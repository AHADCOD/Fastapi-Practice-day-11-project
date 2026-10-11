from fastapi import FastAPI, Depends
from core.exceptions import register_exception_handlers
from routers.book import BookRouter
# from routers.member import MemberRouter



app = FastAPI(title="library Management System")

register_exception_handlers(app)
app.include_router(BookRouter)
# app.include_router(MemberRouter)

@app.get("/")
def root():
    return {"message": "Welcome"}

