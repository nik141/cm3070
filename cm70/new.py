import os
import json
import smtplib
from email.mime.text import MIMEText
import cv2
import time
import threading
import subprocess
from datetime import datetime

# Fetch Gmail SMTP server settings from environment variables
smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", 587))
smtp_user = os.getenv("SMTP_USER")  # Gmail address stored in environment variable
smtp_password = os.getenv("SMTP_PASSWORD")  #Gmail app password stored in environment variable

# Email details
sender_email = smtp_user
receiver_email = os.getenv("RECEIVER_EMAIL")  #receiver email stored in environment variable

# Function to send an email notification using Gmail's SMTP server asynchronously
def send_email(subject, body, description):
    def email_thread():
        # Include size and position descriptions in the email body
        email_body = f"{body}\n\nDescription: {description}"
        msg = MIMEText(email_body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = receiver_email

        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.set_debuglevel(1)  # Enable debug output
                server.ehlo()
                server.starttls()  # Secure the connection
                server.ehlo()  # Re-identify ourselves as an encrypted connection
                server.login(smtp_user, smtp_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())
                print("Email sent successfully!")
        except smtplib.SMTPAuthenticationError as e:
            print(f"SMTP authentication error: {e}")
        except smtplib.SMTPException as e:
            print(f"SMTP error: {e}")
        except Exception as e:
            print(f"Error sending email: {e}")

    # Start the email sending in a separate thread
    threading.Thread(target=email_thread).start()

# Function to save metadata to a JSON file
def save_metadata(filename, object_size, position, description):
    metadata = {
        "object_size": object_size,
        "position": position,
        "description": description
    }
    json_filename = filename.replace('.mp4', '.json')
    try:
        with open(json_filename, 'w') as json_file:
            json.dump(metadata, json_file, indent=4)
        print(f"Metadata saved: {json_filename}")
    except Exception as e:
        print(f"Error saving metadata: {e}")

def describe_intruder(object_size, position, frame_width):
    # Classify intruder size
    size_description = "big" if object_size > 10000 else "small"

    # Determine position in the frame
    x, y, w, h = position
    if x + w / 2 < frame_width / 3:
        position_description = "left"
    elif x + w / 2 > 2 * frame_width / 3:
        position_description = "right"
    else:
        position_description = "center"

    return size_description, position_description

def detect_motion(frame, bg_subtractor_bg, bg_subtractor_diff, kernel):
    # Apply background subtraction
    fg_mask_bg = bg_subtractor_bg.apply(frame)
    fg_mask_bg = cv2.morphologyEx(fg_mask_bg, cv2.MORPH_OPEN, kernel)
    fg_mask_bg = cv2.morphologyEx(fg_mask_bg, cv2.MORPH_CLOSE, kernel)

    # Apply frame differencing
    fg_mask_diff = bg_subtractor_diff.apply(frame)
    fg_mask_diff = cv2.morphologyEx(fg_mask_diff, cv2.MORPH_OPEN, kernel)
    fg_mask_diff = cv2.morphologyEx(fg_mask_diff, cv2.MORPH_CLOSE, kernel)

    # Combine foreground masks
    combined_fg_mask = cv2.bitwise_and(fg_mask_bg, fg_mask_diff)
    combined_fg_mask = cv2.morphologyEx(combined_fg_mask, cv2.MORPH_OPEN, kernel)
    combined_fg_mask = cv2.morphologyEx(combined_fg_mask, cv2.MORPH_CLOSE, kernel)

    # Apply foreground mask thresholding
    _, fg_mask_thresh = cv2.threshold(combined_fg_mask, 50, 255, cv2.THRESH_BINARY)

    # Find contours in the thresholded foreground mask
    contours, _ = cv2.findContours(fg_mask_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Detect motion and draw rectangles around detected objects
    motion_detected = False
    object_size = None
    position = None
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w * h > 8000:  # Adjusted threshold for smaller objects
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            motion_detected = True
            if object_size is None:  # Capture size and position once per detection
                object_size = w * h
                position = (x, y, w, h)

    return motion_detected, frame, object_size, position

# Function to convert video to MP4 using FFmpeg
def convert_to_mp4(input_filename, output_filename):
    try:
        subprocess.run(['ffmpeg', '-i', input_filename, '-vcodec', 'libx264', '-acodec', 'aac', output_filename], check=True)
        print(f"Converted {input_filename} to {output_filename}")
        os.remove(input_filename)  # Remove the original AVI file after conversion
    except subprocess.CalledProcessError as e:
        print(f"Error converting video: {e}")

def record_video(cap, lock, filename, duration=20, bg_subtractor_bg=None, bg_subtractor_diff=None, kernel=None):
    # Save initially in AVI format
    avi_filename = filename.replace('.mp4', '.avi')
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(avi_filename, fourcc, 20.0, (640, 480))
    
    start_time = time.time()
    metadata_saved = False  # Initialize the metadata saved flag
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # Get frame width
    metadata_filename = filename.replace('.mp4', '.json')  # Set metadata filename based on MP4

    while time.time() - start_time < duration:
        with lock:
            ret, frame = cap.read()
        if ret:
            # Detect motion and capture object size and position
            motion_detected, processed_frame, object_size, position = detect_motion(frame, bg_subtractor_bg, bg_subtractor_diff, kernel)
            
            # Save metadata once when motion is first detected
            if motion_detected and not metadata_saved and object_size and position:
                size_description, position_description = describe_intruder(object_size, position, frame_width)  # Get descriptions
                description = f"{size_description} intruder on the {position_description} side"
                print(f"Saving metadata for {metadata_filename}")
                save_metadata(metadata_filename, object_size, position, description)
                metadata_saved = True  # Ensure metadata is saved only once

            out.write(processed_frame)  # Write the frame with rectangles to the video
        else:
            break
    
    out.release()

    # Convert to MP4 after recording
    mp4_filename = avi_filename.replace('.avi', '.mp4')
    convert_to_mp4(avi_filename, mp4_filename)

def stabilize_camera(cap, bg_subtractor_bg, bg_subtractor_diff, kernel, stabilization_time=5):
    """Stabilize the camera by running background subtraction without detecting motion."""
    print(f"Stabilizing camera for {stabilization_time} seconds...")
    start_time = time.time()
    while time.time() - start_time < stabilization_time:
        ret, frame = cap.read()
        if not ret:
            print("Error: Unable to read frame during stabilization.")
            break
        # Feed frames to background subtractors without motion detection
        bg_subtractor_bg.apply(frame)
        bg_subtractor_diff.apply(frame)
        cv2.waitKey(10)  # Small delay to process frames

def main():
    # Define the folder where videos are stored
    video_folder = r'C:\Users\User\Desktop\cm70\Intruder_rec'  # Updated path

    # Ensure the folder exists
    os.makedirs(video_folder, exist_ok=True)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: Unable to open camera.")
        return

    bg_subtractor_bg = cv2.createBackgroundSubtractorMOG2()
    bg_subtractor_diff = cv2.createBackgroundSubtractorMOG2()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # Stabilize the camera and background subtractors
    stabilize_camera(cap, bg_subtractor_bg, bg_subtractor_diff, kernel, stabilization_time=5)

    recording = False
    recording_start_time = 0
    lock = threading.Lock()

    while True:
        with lock:
            ret, frame = cap.read()
        if not ret:
            print("Error: Unable to read frame.")
            break

        # Detect motion
        motion_detected, processed_frame, object_size, position = detect_motion(frame, bg_subtractor_bg, bg_subtractor_diff, kernel)

        if motion_detected and not recording:
            # Generate filename with path
            filename = os.path.join(video_folder, f'intruder_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4')
            print(f"Motion detected! Starting recording: {filename}")
            recording_start_time = time.time()
            recording = True

            # Read the description from metadata file directly after saving
            size_description, position_description = describe_intruder(object_size, position, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
            description = f"{size_description} intruder on the {position_description} side"

            # Send email notification with the description included
            send_email(
                "Intruder Alert!",
                f"Motion detected! Recording started: {filename}",
                description
            )
            
            # Start recording video with metadata capture
            threading.Thread(target=record_video, args=(cap, lock, filename, 20, bg_subtractor_bg, bg_subtractor_diff, kernel)).start()
        elif recording and time.time() - recording_start_time >= 20:
            print("Recording finished.")
            recording = False

        # Show the processed frame with rectangles
        cv2.imshow("Processed Frame", processed_frame)

        # Check for key press to exit
        if cv2.waitKey(30) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
