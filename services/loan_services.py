from datetime import datetime, timedelta, UTC, UTC
from schemas.loans import ReturnStatus
from schemas.books import BookOut
from schemas.members import MemberOut
from .book_services import check_book
from .member_services import check_member
from core.exceptions import BookUnavailableError, LoanNotFoundError, DuplicateLoanError, LoanLimitExceededError

loans = {}

def check_loan(loan_id: int):
    if loan_id not in list(loans.keys()):
        raise LoanNotFoundError(message="Loan not found.")
    return loans[loan_id]


def create_loan_service(member_id: int, book_id: int):
    
    member = check_member(member_id)
    book = check_book(book_id)

    if book["available_copies"] <= 0:
        raise BookUnavailableError(message="Book is currently unavailable for loan.")

    for loan in loans.values():
        if loan["book_id"] == book_id and loan["member_id"] == member_id and loan["status"] == ReturnStatus.ACTICE:
            raise DuplicateLoanError(message="This member already has an active loan for this book.")


    member_loan_count = sum(1 for loan in loans.values() if loan["member_id"] == member_id and loan["status"] == ReturnStatus.ACTICE)

    if (member["membership_type"] == "premium" and member_loan_count >= 10) or (member["membership_type"] == "basic" and member_loan_count >= 3):
        raise LoanLimitExceededError(message="Member has exceeded the loan limit for their membership type.")

    loan_days = 30 if member["membership_type"] == "premium" else 14
    loan_id = max(loans.keys()) + 1 if loans else 1
    due_date = datetime.now(UTC) + timedelta(days=loan_days)

    loan_data = {
        "book_id": book_id,
        "member_id": member_id,
        "loan_date": datetime.now(UTC),
        "due_date": due_date,
        "return_date": None,
        "status": ReturnStatus.ACTICE
    }

    loans[loan_id] = loan_data
    book["available_copies"] -= 1

    return {"id": loan_id, **loan_data, "member": MemberOut(id=member_id, **member), "book": BookOut(id=book_id, **book)}