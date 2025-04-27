from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.database import get_db, Period, Certificate

router = APIRouter()

@router.get("/api/periods/completed")
def get_completed_periods(db: Session = Depends(get_db)):
    periods = db.query(Period).filter(Period.status == '已结束').order_by(Period.end_date.desc()).all()
    # print("查询到的 periods:", periods)  # 打印对象列表
    # for p in periods:
    #     print(f"id={p.id}, period_name={p.period_name}, status={p.status}, end_date={p.end_date}")
    return [
        {"id": p.id, "period_name": p.period_name}
        for p in periods
    ]

@router.get("/api/certificate")
def get_certificate(period_id: int, nickname: str, db: Session = Depends(get_db)):
    # 只查 cer_content 字段
    result = db.query(Certificate.cer_content).filter(
        Certificate.period_id == period_id,
        Certificate.nickname == nickname
    ).first()
    print(f"SQL 查询结果 cer_content: {result.cer_content if result else None}")
    if result and result.cer_content:
        return {"cer_content": result.cer_content}
    else:
        raise HTTPException(status_code=404, detail="Certificate not found")
