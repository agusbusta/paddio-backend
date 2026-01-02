from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.crud import match as crud
from app.schemas.match import MatchResponse, MatchCreate, MatchUpdate
from app.models.match import Match
from app.models.court import MatchStatus

router = APIRouter()


@router.post("/", response_model=MatchResponse)
def create_match(match: MatchCreate, db: Session = Depends(get_db)):
    return crud.create_match(db=db, match=match)


@router.get("/", response_model=List[MatchResponse])
def read_matches(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None, description="Filter by match status"),
    club_id: Optional[int] = Query(None, description="Filter by club ID"),
    start_date: Optional[str] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener lista de partidos.
    
    Solo disponible para super admins.
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can view matches"
        )

    query = db.query(Match)

    # Filtrar por estado
    if status:
        try:
            match_status = MatchStatus(status)
            query = query.filter(Match.status == match_status)
        except ValueError:
            pass  # Ignorar status inválido

    # Filtrar por club (a través de la relación court)
    if club_id:
        from app.models.court import Court
        query = query.join(Court).filter(Court.club_id == club_id)

    # Filtrar por rango de fechas
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Match.start_time >= start_datetime)
        except ValueError:
            pass

    if end_date:
        try:
            from datetime import timedelta
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Match.start_time < end_datetime)
        except ValueError:
            pass

    matches = query.order_by(Match.start_time.desc()).offset(skip).limit(limit).all()

    # Enriquecer con información de jugadores, club, etc.
    enriched_matches = []
    for match in matches:
        match_dict = {
            "id": match.id,
            "court_id": match.court_id,
            "start_time": match.start_time.isoformat() if match.start_time else None,
            "end_time": match.end_time.isoformat() if match.end_time else None,
            "status": match.status.value if match.status else None,
            "score": match.score,
            "created_at": match.created_at.isoformat() if match.created_at else None,
            "creator_id": match.creator_id,
        }

        # Obtener información de la cancha y club
        if match.court:
            match_dict["court_name"] = match.court.name
            if match.court.club:
                match_dict["club_id"] = match.court.club.id
                match_dict["club_name"] = match.court.club.name

        # Obtener información de los jugadores
        if match.players:
            match_dict["players"] = [
                {
                    "id": player.id,
                    "name": player.name,
                    "email": player.email,
                }
                for player in match.players
            ]
        else:
            match_dict["players"] = []

        # Obtener información del creador
        if match.creator:
            match_dict["creator_name"] = match.creator.name
            match_dict["creator_email"] = match.creator.email

        enriched_matches.append(match_dict)

    return enriched_matches


@router.get("/{match_id}", response_model=MatchResponse)
def read_match(match_id: int, db: Session = Depends(get_db)):
    db_match = crud.get_match(db, match_id=match_id)
    if db_match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return db_match


@router.put("/{match_id}", response_model=MatchResponse)
def update_match(match_id: int, match: MatchUpdate, db: Session = Depends(get_db)):
    db_match = crud.update_match(db=db, match_id=match_id, match=match)
    if db_match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return db_match


@router.delete("/{match_id}")
def delete_match(match_id: int, db: Session = Depends(get_db)):
    success = crud.delete_match(db=db, match_id=match_id)
    if not success:
        raise HTTPException(status_code=404, detail="Match not found")
    return {"message": "Match deleted successfully"}
