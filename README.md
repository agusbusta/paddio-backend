# Paddio Backend

Paddio is a backend service for managing padel court bookings and matches. It provides APIs for user authentication, club management, court booking, and match organization.

## Features

- User authentication and authorization
- Club and stadium management
- Court booking system
- Match creation and joining
- Player rating system

## Prerequisites

- Python 3.8+
- PostgreSQL
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd paddio-backend
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:
```env
DATABASE_URL=postgresql://username:password@localhost/paddio
SECRET_KEY=your-secret-key
```

5. Initialize the database:
```bash
# Make sure PostgreSQL is running
# The tables will be created automatically when the application starts
```

## Running the Application

1. Start the server:
```bash
uvicorn app.main:app --reload
```

2. Access the API documentation at:
```
http://localhost:8000/docs
```

## API Endpoints

### Authentication
- POST /auth/register - Register a new user
- POST /auth/token - Login and get access token
- GET /auth/me - Get current user information

## Development

### Project Structure
```
paddio-backend/
├── app/
│   ├── main.py
│   ├── models/
│   │   ├── user.py
│   │   ├── club.py
│   │   └── court.py
│   ├── routers/
│   │   └── auth.py
│   ├── schemas/
│   │   ├── user.py
│   │   └── club.py
│   ├── services/
│   │   └── auth.py
│   ├── database.py
│   └── config.py
├── requirements.txt
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 