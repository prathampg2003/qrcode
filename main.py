from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import qrcode
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mysql.connector
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Form


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Configuration
db_config = {
    'host': 'sql12.freesqldatabase.com',
    'user': 'sql12759159',
    'password': 'v5SaGkWwNS',
    'database': 'sql12759159'
}

# Email Configuration
SMTP_SERVER = 'smtp-relay.sendinblue.com'
SMTP_PORT = 587
SMTP_USER = 'prathampg2003@gmail.com'
SMTP_PASS = 'aQbv7CZdDrckyxw8'

# Pydantic Models for Data Validation
class SubmissionData(BaseModel):
    name: str
    mobile_number: str
    email: str
    number_of_people: int
    date_of_visit: str

class PreRegistrationData(BaseModel):
    name: str
    mobile_number: str
    email: str
    date_of_visit: str

class UpdateData(BaseModel):
    number_of_people: int



def send_email(to_address, subject, body, qr_image, filename="qr-code.jpeg"):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_address
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(qr_image)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={filename}')
    msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_address, msg.as_string())
        server.quit()
        print(f"Email sent to {to_address} successfully.")
    except Exception as e:
        print(f"Error sending email to {to_address}: {e}")

# Initialize Database
def init_db():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            name VARCHAR(255),
            mobile_number VARCHAR(15) PRIMARY KEY,
            email VARCHAR(255),
            qr_link TEXT,
            number_of_people INT,
            date_of_visit DATE,
            scanned BOOLEAN DEFAULT FALSE,
            no_of_visits INT DEFAULT 0
        )
    ''')
    print(f"Connected to database success1: ")
    conn.commit()
    cursor.close()
    conn.close()

@app.post("/submit")
async def submit(data: SubmissionData, request: Request):
    try:
        # Extract data
        name = data.name
        mobile_number = data.mobile_number
        email = data.email
        number_of_people = data.number_of_people
        date_of_visit = data.date_of_visit

        # Generate QR Code
        server_url = str(request.base_url).strip('/')
        qr_code_data = f"{server_url}/verify/{mobile_number}"
        qr = qrcode.make(qr_code_data)
        buffered = io.BytesIO()
        qr.save(buffered, format="JPEG")
        qr_image = buffered.getvalue()

        # Insert into database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO visitors (name, mobile_number, email, qr_link, number_of_people, date_of_visit)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (name, mobile_number, email, qr_code_data, number_of_people, date_of_visit))
        conn.commit()

        # Send Email
        email_subject = 'Your QR Code for Visit'
        email_body = f"Hello {name},\n\nThank you for submitting your details! Please find your QR code attached."
        send_email(email, email_subject, email_body, qr_image)

        cursor.close()
        conn.close()

        return JSONResponse(content={"message": "Form submitted successfully, QR code sent to email."}, status_code=200)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))
    
@app.post("/submit2")
async def submit2(data: PreRegistrationData, request: Request):
    try:
        # Extract data for pre-registered user
        name = data.name
        mobile_number = data.mobile_number
        email = data.email
        date_of_visit = data.date_of_visit

        # Generate QR Code
        server_url = str(request.base_url).strip('/')
        qr_code_data = f"{server_url}/verify/{mobile_number}"
        qr = qrcode.make(qr_code_data)
        buffered = io.BytesIO()
        qr.save(buffered, format="JPEG")
        qr_image = buffered.getvalue()

        # Insert into database without `number_of_people`
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO visitors (name, mobile_number, email, qr_link, date_of_visit)
            VALUES (%s, %s, %s, %s, %s)
        ''', (name, mobile_number, email, qr_code_data, date_of_visit))
        conn.commit()

        # Send Email
        email_subject = 'Your QR Code for Pre-Registration'
        email_body = f"Hello {name},\n\nThank you for pre-registering! Please find your QR code attached."
        send_email(email, email_subject, email_body, qr_image)

        cursor.close()
        conn.close()

        return JSONResponse(content={"message": "Pre-registration successful, QR code sent to email."}, status_code=200)
    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry error
            return HTTPException(status_code=400, detail="Mobile number already registered.")
        return HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))


@app.get("/verify/{mobile_number}")
async def verify(mobile_number: str,request: Request):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute('''
            SELECT name, number_of_people, no_of_visits FROM visitors WHERE mobile_number = %s
        ''', (mobile_number,))
        result = cursor.fetchone()

        if not result:
            return HTTPException(status_code=404, detail="User not found.")

        name, number_of_people, no_of_visits = result

        # If `number_of_people` is not set, return status code 202 and update URL
        if not number_of_people or number_of_people == 0:
            base_url = str(request.base_url).rstrip("/")
            update_url = f"{base_url}/update/{mobile_number}"
            return JSONResponse(content={
                "status": 202,
                "message": "Number of people not specified. Please update the information.",
                "name":name,
                "mobilenumber":mobile_number,
                "update_url": update_url

            }, status_code=202)

        # Increment visit count and mark as scanned
        no_of_visits = (no_of_visits or 0) + 1
        cursor.execute('''
            UPDATE visitors
            SET scanned = TRUE, no_of_visits = %s
            WHERE mobile_number = %s
        ''', (no_of_visits, mobile_number))
        conn.commit()

        cursor.close()
        conn.close()

        return JSONResponse(content={
            "message": f"Hi {name},\nWelcome to the CP meet.\nYour entry is verified."
        }, status_code=200)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))

@app.post("/update/{mobile_number}")
async def update_people(mobile_number: str, data: UpdateData, request: Request):
    try:
        # Extract `number_of_people` from the JSON body
        number_of_people = data.number_of_people

        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute('''
            SELECT * FROM visitors WHERE mobile_number = %s
        ''', (mobile_number,))
        result = cursor.fetchone()

        if not result:
            # If user doesn't exist, return the `/update` URL with 202 status
            return JSONResponse(
                content={
                    "detail": "User not found.",
                    "update_url": f"{request.base_url}update/{mobile_number}"
                },
                status_code=202
            )

        # Update the number of people for the visit
        cursor.execute('''
            UPDATE visitors
            SET number_of_people = %s
            WHERE mobile_number = %s
        ''', (number_of_people, mobile_number))
        conn.commit()

        cursor.close()
        conn.close()

        # Redirect to the `/verify` endpoint
        return await verify(mobile_number, request)
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))

init_db()
