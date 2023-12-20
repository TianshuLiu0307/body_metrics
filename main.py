from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean, func, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship, joinedload
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime

# Database configuration
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://admin:shapementor@shapementor-rds.cuorsbapmndf.us-east-2.rds.amazonaws.com/ShapeMentor"


engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# SQLAlchemy User model
class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hashed_password = Column(String(255), nullable=False)
    activated = Column(Boolean, nullable=False)
    user_name = Column(String(255))
    dob = Column(Date)
    gender = Column(String(50))
    race = Column(String(50))
    email = Column(String(255), nullable=False)
    phone_number = Column(String(20))
    body_metrics = relationship("BodyMetrics", back_populates="user")

# Pydantic models
class UserCreateModel(BaseModel):
    user_id: int
    user_name: str
    dob: Optional[date]
    gender: Optional[str]
    race: Optional[str]
    email: str
    phone_number: Optional[str]
    class Config:
        orm_mode = True

class UserResponseModel(BaseModel):
    user_id: int
    user_name: str
    dob: Optional[date]
    gender: Optional[str]
    race: Optional[str]
    email: str
    phone_number: Optional[str]
    class Config:
        orm_mode = True

class BodyMetrics(Base):
    __tablename__ = "body_metrics"

    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), primary_key=True, index=True)
    metric_index = Column(String(50), ForeignKey("body_metrics_lookup.metric_index"), primary_key=True, index=True)
    value = Column(Float, nullable=False)
    user = relationship("User", back_populates="body_metrics")
    metric = relationship("BodyMetricsLookup", back_populates="body_metrics")

class BodyMetricsLookup(Base):
    __tablename__ = "body_metrics_lookup"
    metric_index = Column(String(50), primary_key=True)
    metric_name = Column(String(255), nullable=False)
    metric_unit = Column(String(50), nullable=False)
    body_metrics = relationship("BodyMetrics", back_populates="metric")

class BodyMetricsResponseModel(BaseModel):
    user_id: int
    timestamp: datetime
    metric_index: str
    value: float

class BodyMetricsCreateModel(BaseModel):
    metric_index: str
    value: float

# FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/create")
def create_user_form(request: Request, db: Session = Depends(get_db)):
    max_id = db.query(func.max(User.user_id)).scalar()
    next_id = (max_id or 0) + 1
    # return templates.TemplateResponse("create_user.html", {"request": request})
    return templates.TemplateResponse("create_user.html", {"request": request, "next_id": next_id})

@app.post("/users/", response_model=UserCreateModel)
def create_user(user_id: str = Form(...),
                user_name: str = Form(...),
                email: EmailStr = Form(...),
                password: str = Form(...),
                dob:  date = Form(None),
                gender:  str = Form(None),
                race: str = Form(None),
                phone_number : str = Form(None),
                db: Session = Depends(get_db)):

    new_user = User(
        user_id = user_id,
        user_name=user_name,
        email=email,
        hashed_password=password,  # Replace with real hash
        activated=True,  # Assuming default activation status
        dob = dob,
        gender = gender,
        race = race,
        phone_number = phone_number
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RedirectResponse(url=f"/users/{new_user.user_id}", status_code=303)

@app.post("/users/{user_id}/add_metric/", response_model=BodyMetricsCreateModel)
def add_body_metric(user_id: int,
                    metric_index: int = Form(...),
                    value: float = Form(...),
                    db: Session = Depends(get_db)):
    timestamp = datetime.now()
    new_metric = BodyMetrics(
        user_id = user_id,
        timestamp = timestamp,
        metric_index = metric_index,
        value = value
    )
    db.add(new_metric)
    db.commit()
    db.refresh(new_metric)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)

@app.get("/users/{user_id}/metrics")
def get_body_metrics_for_user(user_id: int, db: Session = Depends(get_db)):
    body_metrics_records = (
        db.query(BodyMetrics)
        .filter(BodyMetrics.user_id == user_id)
        .options(joinedload(BodyMetrics.metric))
        .all()
    )

    if not body_metrics_records:
        raise HTTPException(status_code=404, detail="No body metrics records found for this user")

    # Now, each record in body_metrics_records should have access to metric_name and metric_unit
    result = []
    for record in body_metrics_records:
        result.append({
            "timestamp": record.timestamp,
            "metric_index": record.metric_index,
            "value": record.value,
            "metric_name": record.metric.metric_name,  # Access metric_name through the relationship
            "metric_unit": record.metric.metric_unit,  # Access metric_unit through the relationship
        })

    return result

@app.get("/users/{user_id}")
def read_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()

    # if user is None:
    #     raise HTTPException(status_code=404, detail="User not found")

    # Query the database to fetch body metrics records for the specified user
    body_metrics_records = (
        db.query(BodyMetrics)
        .filter(BodyMetrics.user_id == user_id)
        .options(joinedload(BodyMetrics.metric))
        .all()
    )


    distinct_metric_names = (
        db.query(BodyMetricsLookup.metric_name)
        .distinct()
        .all()
    )

    # if not body_metrics_records:
    #     raise HTTPException(status_code=404, detail="No body metrics records found for this user")

    result = []
    for record in body_metrics_records:
        result.append({
            "timestamp": record.timestamp,
            "metric_index": record.metric_index,
            "value": record.value,
            "metric_name": record.metric.metric_name,  # Access metric_name through the relationship
            "metric_unit": record.metric.metric_unit,  # Access metric_unit through the relationship
        })

    return templates.TemplateResponse("user.html", {"request": request, "user": user, "body_metrics": result})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8012)
