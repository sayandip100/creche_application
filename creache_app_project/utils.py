import face_recognition

def get_face_encoding(image_path):
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0:
            return None, "No face detected"

        if len(encodings) > 1:
            return None, "Multiple faces detected"

        return encodings[0], None

    except Exception as e:
        return None, f"Image processing error: {str(e)}"