from sqlalchemy import Column, Integer
from sqlalchemy.ext.declarative import declarative_base, declared_attr

Base = declarative_base()


class Model(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
