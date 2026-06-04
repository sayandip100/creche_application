import io
import json
import logging

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from healthcenter.models import (
    Doctor,
    HealthCenter,
    HealthCenterMedicineStock,
    Medicine,
    MedicineStockTransaction,
    Nurse,
    PatientTreatment,
    PatientTreatmentMedicine,
)

logger = logging.getLogger(__name__)


class GeneratePrescriptionAPI(APIView):
    """
    Generate a professional e-Prescription PDF for a patient treatment.

    The PDF is generated via an external PDF generation service,
    stored in PatientTreatment.prescription_image, and automatically
    sent via WhatsApp to the patient's contact number.
    Medicine quantity prescribed is deducted from HealthCenterMedicineStock.

    Endpoint: POST /prescription/generate/

    Request Parameters:
    - health_center_id (required): Health Center ID
    - nurse_id (required): Nurse (head nurse) ID
    - doctor_id (required): Doctor ID
    - patient_treatment_id (required): Patient Treatment ID
    - medicines (required): JSON array of prescribed medicines
        [{"id": 1, "quantity": 10},
         {"id": 2, "quantity": 5}]
    - send_whatsapp (optional): Boolean (default: true)

    Response:
    {
        "status_code": 200,
        "message": "Prescription generated successfully",
        "data": {
            "prescription_id": 123,
            "prescription_url": "https://...",
            "patient": { ... },
            "doctor": { ... },
            "medicines": [ ... ],
            "stock_deductions": [ ... ],
            "whatsapp_status": "sent|failed|skipped",
            ...
        }
    }
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            # ============================================
            # EXTRACT AND VALIDATE PARAMETERS
            # ============================================
            health_center_id = request.data.get('health_center_id')
            nurse_id = request.data.get('nurse_id')
            doctor_id = request.data.get('doctor_id')
            patient_treatment_id = request.data.get('patient_treatment_id')
            medicines_data = request.data.get('medicines')
            send_whatsapp = request.data.get('send_whatsapp', 'true')

            # Validate required fields
            required_fields = {
                'health_center_id': health_center_id,
                'nurse_id': nurse_id,
                'doctor_id': doctor_id,
                'patient_treatment_id': patient_treatment_id,
                'medicines': medicines_data,
            }
            missing = [k for k, v in required_fields.items() if not v]
            if missing:
                return Response({
                    'status_code': 400,
                    'message': f'Missing required fields: {", ".join(missing)}',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            # Parse medicines JSON
            if isinstance(medicines_data, str):
                try:
                    medicines_list = json.loads(medicines_data)
                except json.JSONDecodeError:
                    return Response({
                        'status_code': 400,
                        'message': 'medicines must be a valid JSON array',
                        'data': {}
                    }, status=status.HTTP_400_BAD_REQUEST)
            elif isinstance(medicines_data, list):
                medicines_list = medicines_data
            else:
                return Response({
                    'status_code': 400,
                    'message': 'medicines must be a JSON array',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            if not medicines_list:
                return Response({
                    'status_code': 400,
                    'message': 'At least one medicine is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            send_whatsapp_bool = str(send_whatsapp).lower() in ['true', '1', 'yes']

            # ============================================
            # VERIFY FOREIGN KEY REFERENCES
            # ============================================
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                nurse = Nurse.objects.select_related('user').get(id=nurse_id, is_active=True)
            except Nurse.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Nurse not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                doctor = Doctor.objects.select_related('user').get(id=doctor_id, is_active=True)
            except Doctor.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Doctor not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                treatment = PatientTreatment.objects.get(id=patient_treatment_id)
            except PatientTreatment.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Patient treatment record not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)

            # ============================================
            # UPDATE TREATMENT - set doctor & nurse
            # ============================================
            treatment.doctor = doctor
            treatment.nurse = nurse
            treatment.status = 2  # Completed
            treatment.save()

            # ============================================
            # PROCESS MEDICINES & DEDUCT STOCK
            # ============================================
            saved_medicines = []
            stock_deductions = []
            insufficient_stock = []
            stocks_to_update = []  # For bulk_update
            transactions_to_create = []  # For bulk_create
            medicines_to_create = []  # For bulk_create

            # Clear existing medicines for re-prescription
            treatment.medicines.all().delete()

            for med_item in medicines_list:
                medicine_id = med_item.get('id') or med_item.get('medicine_id')
                quantity = med_item.get('quantity', 0)

                if not medicine_id or not quantity:
                    continue

                try:
                    medicine = Medicine.objects.get(id=medicine_id)
                except Medicine.DoesNotExist:
                    continue

                try:
                    quantity = int(quantity)
                except (ValueError, TypeError):
                    continue

                if quantity <= 0:
                    continue

                # Deduct from HealthCenterMedicineStock
                try:
                    stock = HealthCenterMedicineStock.objects.get(
                        health_center=health_center,
                        medicine=medicine
                    )
                except HealthCenterMedicineStock.DoesNotExist:
                    insufficient_stock.append({
                        'medicine_id': medicine.id,
                        'medicine_name': medicine.medicine_name,
                        'reason': 'No stock record found for this health center'
                    })
                    continue

                if stock.current_stock_qty < quantity:
                    insufficient_stock.append({
                        'medicine_id': medicine.id,
                        'medicine_name': medicine.medicine_name,
                        'requested': quantity,
                        'available': stock.current_stock_qty,
                        'reason': 'Insufficient stock'
                    })
                    continue

                # Deduct stock (to be batch updated)
                old_stock = stock.current_stock_qty
                stock.current_stock_qty -= quantity
                stocks_to_update.append(stock)

                # Prepare transaction record
                transactions_to_create.append(
                    MedicineStockTransaction(
                        health_center=health_center,
                        medicine=medicine,
                        transaction_type='OUT',
                        quantity=quantity,
                        reference_type='PRESCRIPTION',
                        reference_id=treatment.id,
                        remarks=f"Prescribed for patient: {treatment.patient_name}"
                    )
                )

                # Prepare medicine record
                medicines_to_create.append(
                    PatientTreatmentMedicine(
                        treatment=treatment,
                        medicine=medicine,
                        prescribed_qty=quantity,
                        issued_qty=quantity,
                        notes=f"Prescribed by Dr. {doctor.name or doctor.user.username}"
                    )
                )

                saved_medicines.append({
                    'medicine_id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'medicine_code': medicine.medicine_code,
                    'quantity': quantity,
                })

                stock_deductions.append({
                    'medicine_id': medicine.id,
                    'medicine_name': medicine.medicine_name,
                    'previous_stock': old_stock,
                    'deducted': quantity,
                    'remaining_stock': stock.current_stock_qty,
                })

            if not saved_medicines:
                return Response({
                    'status_code': 400,
                    'message': 'No medicines could be prescribed. Check stock availability.',
                    'data': {
                        'insufficient_stock': insufficient_stock
                    }
                }, status=status.HTTP_400_BAD_REQUEST)

            # ============================================
            # BATCH UPDATE ALL TABLES (ATOMIC)
            # ============================================
            try:
                # Batch update stock
                if stocks_to_update:
                    HealthCenterMedicineStock.objects.bulk_update(
                        stocks_to_update, 
                        ['current_stock_qty', 'last_updated_at'],
                        batch_size=100
                    )
                    logger.info(f"Stock updated for {len(stocks_to_update)} medicines")

                # Batch create transactions
                if transactions_to_create:
                    created_transactions = MedicineStockTransaction.objects.bulk_create(
                        transactions_to_create,
                        batch_size=100
                    )
                    logger.info(f"Created {len(created_transactions)} stock transaction records")

                # Batch create treatment medicines
                if medicines_to_create:
                    created_medicines = PatientTreatmentMedicine.objects.bulk_create(
                        medicines_to_create,
                        batch_size=100
                    )
                    logger.info(f"Created {len(created_medicines)} treatment medicine records")

            except Exception as e:
                logger.error(f"Batch update failed: {e}", exc_info=True)
                raise  # Re-raise to trigger transaction rollback

            # ============================================
            # BUILD PRESCRIPTION DATA FOR PDF
            # ============================================
            prescription_data = self._build_prescription_data(
                treatment, health_center, doctor, nurse, saved_medicines
            )

            # ============================================
            # GENERATE PRESCRIPTION PDF LOCALLY
            # ============================================
            pdf_generated = False
            pdf_error = None
            prescription_image_url = None

            try:
                # Try to generate PDF
                pdf_content = self._generate_local_pdf(prescription_data)
                
                # If main PDF generation fails, use minimal fallback
                if not pdf_content:
                    logger.warning("Main PDF generation returned None, using fallback")
                    pdf_content = self._create_minimal_pdf_placeholder(prescription_data)
                
                # Save the PDF if we have content
                if pdf_content:
                    file_name = f"prescription_{treatment.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    treatment.prescription_image.save(file_name, ContentFile(pdf_content), save=True)
                    pdf_generated = True
                    logger.info(f"PDF saved successfully: {file_name}")
                else:
                    pdf_error = "Failed to generate PDF content"
                    logger.error(pdf_error)
            except Exception as e:
                pdf_error = str(e)
                logger.error(f"PDF generation failed: {e}", exc_info=True)

            # Always build URL after save attempt (whether from new generation or existing)
            if treatment.prescription_image:
                prescription_image_url = request.build_absolute_uri(treatment.prescription_image.url)
            elif not prescription_image_url and pdf_error:
                # Log that we couldn't generate URL
                logger.error(f"Could not build prescription URL. PDF error: {pdf_error}")

            # ============================================
            # SEND VIA WHATSAPP
            # ============================================
            whatsapp_status = 'skipped'
            whatsapp_details = 'WhatsApp sending was skipped'
            whatsapp_sent = False

            if send_whatsapp_bool and prescription_image_url and treatment.contact_number:
                try:
                    whatsapp_result = self._send_whatsapp_prescription(
                        treatment,
                        prescription_image_url
                    )
                    whatsapp_status = whatsapp_result.get('status', 'failed')
                    whatsapp_details = whatsapp_result.get('message', '')
                    whatsapp_sent = (whatsapp_status == 'sent')
                except Exception as e:
                    whatsapp_status = 'failed'
                    whatsapp_details = str(e)
                    logger.error(f"WhatsApp send failed: {e}")

            # Update WhatsApp tracking fields
            treatment.whatsapp_sent = whatsapp_sent
            if whatsapp_sent:
                treatment.whatsapp_sent_at = timezone.now()
            treatment.save()

            # ============================================
            # BUILD RESPONSE
            # ============================================
            return Response({
                'status_code': 200,
                'message': 'Prescription generated successfully',
                'data': {
                    'prescription_id': treatment.id,
                    'prescription_url': prescription_image_url,
                    'pdf_generated': pdf_generated,
                    'pdf_error': pdf_error,
                    'patient': {
                        'id': treatment.id,
                        'name': treatment.patient_name,
                        'age': treatment.age,
                        'contact_number': treatment.contact_number,
                        'remarks': treatment.remarks,
                    },
                    'health_center': {
                        'id': health_center.id,
                        'name': health_center.name,
                    },
                    'nurse': {
                        'id': nurse.id,
                        'name': nurse.nurse_name or nurse.user.username,
                    },
                    'doctor': {
                        'id': doctor.id,
                        'name': doctor.name or doctor.user.username,
                        'qualification': doctor.qualification,
                        'specialization': doctor.specialization,
                    },
                    'prescription_data': {
                        'medicines': saved_medicines,
                        'generated_at': timezone.now().isoformat(),
                    },
                    'stock_deductions': stock_deductions,
                    'insufficient_stock': insufficient_stock,
                    'whatsapp_status': whatsapp_status,
                    'whatsapp_details': whatsapp_details,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Prescription generation error")
            return Response({
                'status_code': 500,
                'message': f'Prescription generation error: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_prescription_data(self, treatment, health_center, doctor, nurse, medicines):
        """Build structured prescription data for the PDF generation API."""
        return {
            'prescription_id': treatment.id,
            'health_center': {
                'name': health_center.name,
                'address': health_center.location_name or '',
            },
            'patient': {
                'name': treatment.patient_name,
                'age': treatment.age,
                'contact': treatment.contact_number,
                'remarks': treatment.remarks or '',
            },
            'doctor': {
                'name': doctor.name or doctor.user.username,
                'qualification': doctor.qualification or '',
                'specialization': doctor.specialization or '',
            },
            'nurse': {
                'name': nurse.nurse_name or nurse.user.username,
            },
            'medicines': medicines,
            'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _generate_local_pdf(self, data):
        """Generate a professional PDF prescription using reportlab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                SimpleDocTemplate,
            )
            from reportlab.lib.enums import TA_CENTER

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                topMargin=20*mm,
                bottomMargin=20*mm,
                leftMargin=20*mm,
                rightMargin=20*mm,
            )

            styles = getSampleStyleSheet()
            story = []

            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=18,
                spaceAfter=6,
                textColor=colors.HexColor('#1a5276'),
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=6,
                spaceBefore=12,
                textColor=colors.HexColor('#2c3e50'),
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=4,
                leading=16,
            )

            # Header
            hc_name = data.get('health_center', {}).get('name', 'Health Center')
            hc_address = data.get('health_center', {}).get('address', '')

            story.append(Paragraph(f"<b><font size=14>{hc_name}</font></b>", title_style))
            if hc_address:
                story.append(Paragraph(hc_address, normal_style))
            story.append(Paragraph(f"<b>Prescription #{data.get('prescription_id', 'N/A')}</b>", normal_style))
            story.append(Paragraph(f"Date: {data.get('generated_at', '')}", normal_style))
            story.append(Spacer(1, 6*mm))
            story.append(Paragraph("_" * 80, normal_style))
            story.append(Spacer(1, 4*mm))

            # Patient & Doctor Info
            patient = data.get('patient', {})
            doctor = data.get('doctor', {})
            nurse = data.get('nurse', {})

            # Create Paragraph objects for table cells to support HTML formatting
            patient_name_para = Paragraph(f"<b>{patient.get('name', 'N/A')}</b>", normal_style)
            doctor_name_para = Paragraph(f"<b>{doctor.get('name', 'N/A')}</b>", normal_style)
            age_para = Paragraph(f"{patient.get('age', 'N/A')}", normal_style)
            qualification_para = Paragraph(f"{doctor.get('qualification', '')}", normal_style)
            contact_para = Paragraph(f"{patient.get('contact', '')}", normal_style)
            specialization_para = Paragraph(f"{doctor.get('specialization', '')}", normal_style)
            nurse_name_para = Paragraph(f"{nurse.get('name', 'N/A')}", normal_style)

            info_data = [
                [Paragraph('Patient Name:', normal_style), patient_name_para,
                 Paragraph('Doctor:', normal_style), doctor_name_para],
                [Paragraph('Age:', normal_style), age_para,
                 Paragraph('Qualification:', normal_style), qualification_para],
                [Paragraph('Contact:', normal_style), contact_para,
                 Paragraph('Specialization:', normal_style), specialization_para],
                [Paragraph('Nurse:', normal_style), nurse_name_para, Paragraph('', normal_style), Paragraph('', normal_style)],
            ]

            info_table = Table(info_data, colWidths=[70, 180, 70, 180])
            info_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 6*mm))

            # Remarks from patient treatment
            remarks = patient.get('remarks', '')
            if remarks:
                story.append(Paragraph("<b>REMARKS</b>", heading_style))
                story.append(Paragraph(remarks, normal_style))
                story.append(Spacer(1, 3*mm))

            # Medicines Table
            story.append(Paragraph("<b>PRESCRIBED MEDICINES</b>", heading_style))
            med_list = data.get('medicines', [])

            if med_list:
                med_table_data = [
                    ['#', 'Medicine', 'Quantity']
                ]
                for idx, med in enumerate(med_list, 1):
                    med_table_data.append([
                        str(idx),
                        med.get('medicine_name', ''),
                        str(med.get('quantity', '')),
                    ])

                med_table = Table(med_table_data, colWidths=[30, 300, 170])
                med_table.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(med_table)
            else:
                story.append(Paragraph("No medicines prescribed.", normal_style))

            # Footer
            story.append(Spacer(1, 10*mm))
            story.append(Paragraph("_" * 80, normal_style))
            story.append(Paragraph(
                "<i>This is a computer-generated prescription.</i>",
                ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
            ))

            doc.build(story)
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if pdf_content:
                logger.info(f"PDF generated successfully, size: {len(pdf_content)} bytes")
                return pdf_content
            else:
                logger.error("PDF buffer is empty after build")
                return None

        except ImportError as ie:
            logger.warning(f"reportlab not installed: {ie}. Install with: pip install reportlab")
            return None
        except Exception as e:
            logger.error(f"Error in _generate_local_pdf: {e}", exc_info=True)
            return None

    def _create_minimal_pdf_placeholder(self, data):
        """Create a minimal PDF with prescription info as fallback."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            c.setFont("Helvetica-Bold", 16)
            hc_name = data.get('health_center', {}).get('name', 'Health Center')
            c.drawString(50, height - 50, hc_name)

            c.setFont("Helvetica", 10)
            c.drawString(50, height - 70, f"Prescription #{data.get('prescription_id', 'N/A')}")
            c.drawString(50, height - 85, f"Date: {data.get('generated_at', '')}")

            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, height - 120, "Patient Details")
            c.setFont("Helvetica", 10)
            patient = data.get('patient', {})
            c.drawString(50, height - 140, f"Name: {patient.get('name', 'N/A')}")
            c.drawString(50, height - 155, f"Age: {patient.get('age', 'N/A')}")
            c.drawString(50, height - 170, f"Contact: {patient.get('contact', '')}")

            remarks = patient.get('remarks', '')
            if remarks:
                c.drawString(50, height - 185, f"Remarks: {remarks[:100]}")

            c.setFont("Helvetica-Bold", 12)
            c.drawString(300, height - 120, "Doctor Details")
            c.setFont("Helvetica", 10)
            doctor = data.get('doctor', {})
            c.drawString(300, height - 140, f"Dr. {doctor.get('name', 'N/A')}")
            c.drawString(300, height - 155, f"{doctor.get('qualification', '')}")
            c.drawString(300, height - 170, f"{doctor.get('specialization', '')}")

            y = height - 220
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Prescribed Medicines")
            y -= 20
            c.setFont("Helvetica", 10)
            for med in data.get('medicines', []):
                c.drawString(50, y, f"- {med.get('medicine_name', '')} x {med.get('quantity', '')}")
                y -= 15

            c.save()
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if pdf_content:
                logger.info(f"Minimal PDF fallback generated, size: {len(pdf_content)} bytes")
                return pdf_content
            else:
                logger.error("Minimal PDF buffer is empty")
                return None

        except ImportError as ie:
            logger.error(f"reportlab canvas not available: {ie}")
            return None
        except Exception as e:
            logger.error(f"Error in _create_minimal_pdf_placeholder: {e}", exc_info=True)
            return None

    def _send_whatsapp_prescription(self, treatment, prescription_url):
        """Send the prescription to the patient's WhatsApp number."""
        if not treatment.contact_number:
            return {'status': 'skipped', 'message': 'No contact number available'}

        phone = ''.join(filter(str.isdigit, treatment.contact_number))
        if not phone:
            return {'status': 'failed', 'message': 'Invalid contact number'}

        message = (
            f"🏥 *Prescription from Health Center*\n\n"
            f"Dear *{treatment.patient_name}*,\n\n"
            f"Your prescription has been generated. Please find it below:\n"
            f"📄 {prescription_url}\n\n"
            f"*Prescription ID:* #{treatment.id}\n"
            f"*Date:* {treatment.created_at.strftime('%d-%b-%Y')}\n\n"
            f"⚠️ *Important:*\n"
            f"• Follow the dosage as prescribed\n"
            f"• Complete the full course of medication\n"
            f"• Contact your doctor if symptoms persist\n\n"
            f"*Thank you,*\n"
            f"Health Center Team"
        )

        try:
            whatsapp_api_url = "http://45.64.107.97:5010/api/v1/whatsapp/send"

            payload = {
                'phone': phone,
                'message': message,
                'media_url': prescription_url,
                'media_type': 'document',
                'filename': f'prescription_{treatment.id}.pdf',
            }

            response = requests.post(
                whatsapp_api_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    'status': 'sent',
                    'message': f"WhatsApp message sent to {phone}",
                    'api_response': result
                }
            else:
                logger.warning(f"WhatsApp API returned {response.status_code}: {response.text[:200]}")
                return {
                    'status': 'failed',
                    'message': f"WhatsApp API error: {response.status_code}",
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API call failed: {e}")
            return {
                'status': 'failed',
                'message': f"Failed to send WhatsApp: {str(e)}",
            }


class MedicineListAPI(APIView):
    """
    Fetch list of all active medicines with their stock count at a health center.
    
    Endpoint: POST /medicine/list/
    
    Request Body: {
        "health_center_id": 1
    }
    
    Response:
    {
        "status_code": 200,
        "message": "Medicines fetched successfully",
        "data": {
            "medicines": [
                {
                    "id": 1,
                    "name": "Medicine 1",
                    "code": "MED001",
                    "unit": "Unit",
                    "min_stock_level": 5,
                    "current_stock_qty": 15,
                    "last_updated_at": "2026-06-02T04:48:04.848195+00:00",
                    "is_low_stock": false
                },
                ...
            ],
            "total_count": 10,
            "health_center_id": 1
        }
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            health_center_id = request.data.get('health_center_id')
            
            if not health_center_id:
                return Response({
                    'status_code': 400,
                    'message': 'health_center_id is required',
                    'data': {}
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate health center exists
            try:
                health_center = HealthCenter.objects.get(id=health_center_id)
            except HealthCenter.DoesNotExist:
                return Response({
                    'status_code': 404,
                    'message': 'Health center not found',
                    'data': {}
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Fetch all active medicines
            medicines = Medicine.objects.filter(is_active=True).order_by('medicine_name')
            
            # Pre-fetch all stock records for this health center in one query
            stock_records = {
                s.medicine_id: s
                for s in HealthCenterMedicineStock.objects.filter(health_center=health_center)
            }
            
            medicines_data = []
            for medicine in medicines:
                stock = stock_records.get(medicine.id)
                
                if stock:
                    current_stock_qty = stock.current_stock_qty
                    last_updated_at = stock.last_updated_at.isoformat()
                else:
                    current_stock_qty = 0
                    last_updated_at = None
                
                medicines_data.append({
                    'id': medicine.id,
                    'name': medicine.medicine_name,
                    'code': medicine.medicine_code or '',
                    'unit': medicine.unit_name,
                    'min_stock_level': medicine.min_stock_level,
                    'current_stock_qty': current_stock_qty,
                    'last_updated_at': last_updated_at,
                    'is_low_stock': current_stock_qty < medicine.min_stock_level if stock else True,
                })
            
            return Response({
                'status_code': 200,
                'message': 'Medicines fetched successfully',
                'data': {
                    'medicines': medicines_data,
                    'total_count': len(medicines_data),
                    'health_center_id': health_center.id
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception("Error fetching medicines")
            return Response({
                'status_code': 500,
                'message': f'Error fetching medicines: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MedicineDetailAPI(APIView):
    """
    Fetch details of a specific medicine including stock at all health centers.
    
    Endpoint: GET /medicine/<medicine_id>/
    
    Response:
    {
        "status_code": 200,
        "message": "Medicine details fetched",
        "data": {
            "id": 1,
            "name": "Medicine 1",
            "code": "MED001",
            "unit": "Unit",
            "min_stock_level": 5,
            "is_active": true,
            "created_at": "2026-06-02T04:48:04.848195+00:00",
            "stock_across_centers": [
                {
                    "health_center_id": 1,
                    "health_center_name": "Health Center 1",
                    "current_stock_qty": 15,
                    "last_updated_at": "2026-06-02T04:48:04.848195+00:00"
                }
            ]
        }
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, medicine_id):
        try:
            medicine = Medicine.objects.get(id=medicine_id)
            
            # Get stock across all health centers
            stocks = HealthCenterMedicineStock.objects.filter(medicine=medicine).select_related('health_center')
            
            stock_data = [
                {
                    'health_center_id': stock.health_center.id,
                    'health_center_name': stock.health_center.name,
                    'current_stock_qty': stock.current_stock_qty,
                    'last_updated_at': stock.last_updated_at.isoformat(),
                    'is_low_stock': stock.current_stock_qty < medicine.min_stock_level
                }
                for stock in stocks
            ]
            
            return Response({
                'status_code': 200,
                'message': 'Medicine details fetched',
                'data': {
                    'id': medicine.id,
                    'name': medicine.medicine_name,
                    'code': medicine.medicine_code or '',
                    'unit': medicine.unit_name,
                    'min_stock_level': medicine.min_stock_level,
                    'is_active': medicine.is_active,
                    'created_at': medicine.created_at.isoformat(),
                    'stock_across_centers': stock_data,
                    'total_stock': sum(s['current_stock_qty'] for s in stock_data)
                }
            }, status=status.HTTP_200_OK)
        
        except Medicine.DoesNotExist:
            return Response({
                'status_code': 404,
                'message': 'Medicine not found',
                'data': {}
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.exception("Error fetching medicine details")
            return Response({
                'status_code': 500,
                'message': f'Error fetching medicine details: {str(e)}',
                'data': {}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)