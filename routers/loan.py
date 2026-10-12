from fastapi import APIRouter, Depends, status, Body
from schemas.loans import LoanOut
from services.loan_services import create_loan_service
from core.dependencies import require_admin


LoanRouter = APIRouter(prefix="/loans", tags=["Loan"])

@LoanRouter.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_loan(member_id : int = Body(embed=True, gt=0), book_id : int = Body(embed=True, gt=0)):
    return create_loan_service(member_id, book_id)