"""
YOLO Helmet Detection Module
==============================
Replace the simulate_detection() function in app.py with this module
for actual YOLOv8-based helmet detection.

Installation:
    pip install ultralytics opencv-python-headless

Model:
    Download a pretrained helmet detection model:
    - Option 1: Train your own on helmet dataset (Roboflow: helmet-detection dataset)
    - Option 2: Use pretrained: https://github.com/niconielsen32/ComputerVision/helmet-detection
    - Option 3: Use YOLOv8n pretrained and fine-tune on helmet dataset

Usage:
    Replace simulate_detection() in app.py with detect_helmet_yolo()
"""

import cv2
import numpy as np
import base64
import io
from PIL import Image

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("YOLOv8 not installed. Using simulation mode.")


class HelmetDetector:
    def __init__(self, model_path='helmet_model.pt'):
        """
        Initialize the helmet detector.
        
        Args:
            model_path: Path to the trained YOLOv8 model weights (.pt file)
                       Use 'yolov8n.pt' for base model (no helmet detection)
                       Use custom trained model for helmet detection
        """
        self.model = None
        self.model_path = model_path
        self.class_names = {0: 'Helmet', 1: 'No Helmet', 2: 'Rider'}
        
        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                print(f"✅ YOLO model loaded: {model_path}")
            except Exception as e:
                print(f"⚠️  Could not load model {model_path}: {e}")
                print("    Using simulation mode.")

    def detect(self, image_b64=None, image_path=None, confidence_threshold=0.5):
        """
        Run helmet detection on an image.
        
        Args:
            image_b64: Base64 encoded image string
            image_path: Path to image file
            confidence_threshold: Minimum confidence for detection
            
        Returns:
            dict with:
                - helmet_detected: bool
                - no_helmet_detected: bool
                - confidence: float
                - bounding_boxes: list of detection dicts
                - annotated_image_b64: base64 annotated image
        """
        if self.model is None:
            return self._simulate_detection()

        # Load image
        if image_b64:
            img_data = base64.b64decode(image_b64.split(',')[-1])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif image_path:
            img = cv2.imread(image_path)
        else:
            return self._simulate_detection()

        if img is None:
            return self._simulate_detection()

        # Run YOLOv8 inference
        results = self.model(img, conf=confidence_threshold, verbose=False)

        helmet_detected = False
        no_helmet_detected = False
        max_confidence = 0.0
        bounding_boxes = []

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    label = self.class_names.get(cls_id, f'Class {cls_id}')

                    if conf > max_confidence:
                        max_confidence = conf

                    if label == 'Helmet':
                        helmet_detected = True
                    elif label == 'No Helmet':
                        no_helmet_detected = True

                    bounding_boxes.append({
                        'x': x1, 'y': y1,
                        'w': x2 - x1, 'h': y2 - y1,
                        'label': label,
                        'conf': conf
                    })

                    # Draw on image
                    color = (0, 255, 0) if label == 'Helmet' else (0, 0, 255)
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(img, f'{label} {conf:.1%}',
                               (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                               0.6, color, 2)

        # Encode annotated image back to base64
        _, buffer = cv2.imencode('.jpg', img)
        annotated_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()

        return {
            'helmet_detected': helmet_detected,
            'no_helmet_detected': no_helmet_detected,
            'confidence': max_confidence,
            'bounding_boxes': bounding_boxes,
            'annotated_image_b64': annotated_b64
        }

    def _simulate_detection(self):
        """Fallback simulation when model is not available."""
        import random
        detected = random.choice([True, True, True, False])
        confidence = round(random.uniform(0.82, 0.99), 2)
        return {
            'helmet_detected': not detected,
            'no_helmet_detected': detected,
            'confidence': confidence,
            'bounding_boxes': [],
            'annotated_image_b64': None
        }


def detect_from_video(video_path, detector, output_path='output_detected.mp4'):
    """
    Process a video file for helmet detection.
    Saves annotated video with detection overlays.
    
    Args:
        video_path: Path to input video
        detector: HelmetDetector instance
        output_path: Path to save annotated video
        
    Returns:
        list of detected violations (frame number, confidence)
    """
    if not YOLO_AVAILABLE:
        print("YOLOv8 not available. Cannot process video.")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    violations = []
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Only detect every 5th frame for performance
        if frame_num % 5 == 0:
            _, buffer = cv2.imencode('.jpg', frame)
            img_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()
            result = detector.detect(image_b64=img_b64)

            if result['no_helmet_detected']:
                violations.append({
                    'frame': frame_num,
                    'timestamp': frame_num / fps,
                    'confidence': result['confidence']
                })
                cv2.putText(frame, '⚠ NO HELMET DETECTED',
                           (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                           1.5, (0, 0, 255), 3)

        out.write(frame)
        frame_num += 1

    cap.release()
    out.release()
    print(f"✅ Video processed: {frame_num} frames, {len(violations)} violations found")
    return violations


# ─── Dataset Preparation Guide ───────────────────────────────────────────────
"""
TRAINING YOUR OWN MODEL
========================

1. Dataset Sources:
   - Roboflow: https://universe.roboflow.com/search?q=helmet+detection
   - Kaggle: "helmet detection dataset"
   - IIIT-H Helmet Dataset

2. Dataset Structure (YOLO format):
   dataset/
   ├── images/
   │   ├── train/   (80% of images)
   │   ├── val/     (10% of images)
   │   └── test/    (10% of images)
   └── labels/
       ├── train/   (.txt files with YOLO annotations)
       ├── val/
       └── test/

3. dataset.yaml:
   path: ./dataset
   train: images/train
   val: images/val
   nc: 2  # number of classes
   names: ['Helmet', 'No Helmet']

4. Training command:
   from ultralytics import YOLO
   model = YOLO('yolov8n.pt')
   model.train(data='dataset.yaml', epochs=100, imgsz=640, batch=16)

5. The trained model will be saved to:
   runs/detect/train/weights/best.pt
   
   Use this path as model_path in HelmetDetector('runs/detect/train/weights/best.pt')
"""
