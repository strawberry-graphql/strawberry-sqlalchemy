# Small self-contained Flask app to demonstrate basic strawberry-sqlalchemy-mapper use
import strawberry
from flask import Flask
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from strawberry.flask.views import GraphQLView

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

Base = declarative_base()


class Employee(Base):
    __tablename__ = "employee"
    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String, nullable=False)


strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()


@strawberry_sqlalchemy_mapper.type(Employee)
class Employee:
    pass


@strawberry.type
class EmployeeQuery:
    @strawberry.field
    def employee(self, id: str):
        return Employee(id=id, name="John Doe")


app = Flask(__name__)

schema = strawberry.Schema(
    query=EmployeeQuery,
)

app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view("graphql_view", schema=schema),
)
