from sqlalchemy import create_engine, MetaData, Table, Integer, String, \
    Column, DateTime, ForeignKey, Numeric, SmallInteger, Text, null, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from sqlalchemy import event
import os

from datetime import datetime

Base = declarative_base()

### Tables
#-----------------------------------------
class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer(), primary_key = True, unique = True)
    join_time = Column(DateTime(), default = datetime.now)

    wls = relationship("Wishlist")
    searh = relationship("LastSearchOption", backref = 'last_search_options', uselist = False)

class Wishlist(Base):
    __tablename__ = 'wishlists'
    whishlist_id = Column(Integer(), primary_key = True, unique = True, autoincrement = True)
    user_id = Column(Integer(), ForeignKey('users.user_id'))
    scholarship_id = Column(Integer(), ForeignKey('short_info.scholarship_id'))
    time_added = Column(DateTime(), default = datetime.now)

class LastSearchOption(Base):
    __tablename__ = 'last_search_options'
    user_id = Column(Integer(), ForeignKey('users.user_id'), primary_key = True)
    #deadline = Column(DateTime(), nullable = False)
    country = Column(Text(), nullable = False)
    sorting = Column(Text(), nullable = False)
    ascending = Column(Boolean(), nullable=False)

class ShortInfoTable(Base):
    __tablename__ = 'short_info'
    scholarship_id = Column(Integer(), nullable=False, primary_key = True, unique = True)
    title = Column(Text(), nullable=False)
    link = Column(Text(), nullable=False)
    university_title = Column(Text(), nullable=False)
    deadline = Column(Text(), nullable = False)
    actual_deadline = Column(DateTime(), nullable = False)
    country = Column(Text(), nullable = False)
    comment = Column(Text(), nullable = True)
    rating = Column(Integer(), nullable = False)

    wishlists = relationship('Wishlist')
    fullinfo = relationship('FullInfoTable', backref = 'full_info', uselist = False)

class FullInfoTable(Base):
    __tablename__ = 'full_info'
    scholarship_id = Column(Integer(), ForeignKey('short_info.scholarship_id'), primary_key = True)
    description = Column(Text(), nullable = False)
    field = Column(Text(), nullable = False)
    scholarship_amount = Column(Text(), nullable=True)
    audithory = Column(Text(), nullable = True )
    scholarship_value = Column(Text(), nullable = True)
    website = Column(Text(), nullable = True)

class UsefulInfo(Base):
    __tablename__ = 'useful_info'
    record_id = Column(Integer(), primary_key = True, autoincrement = True)
    title = Column(Text(), nullable = False)
    link = Column(Text(), nullable = False)

#-----------------------------------------

### Utils
#-----------------------------------------
def create_schema(engine):
    Base.metadata.create_all(engine)

def delete_schema(engine):
    Base.metadata.drop_all(engine)
#-----------------------------------------

## Triggers
#-----------------------------------------
@event.listens_for(Wishlist, "after_insert")
def increase_rating(mapper, connection, target):
    table_to_update = ShortInfoTable.__table__

    value_to_update = connection.execute(table_to_update.select()\
        .where(table_to_update.c.scholarship_id == target.scholarship_id)).first()[-1]
    value_to_update += 1
    connection.execute(table_to_update.update().where(table_to_update.c.scholarship_id == target.scholarship_id).values(rating = value_to_update))

@event.listens_for(Wishlist, "after_delete")
def increase_rating(mapper, connection, target):
    table_to_update = ShortInfoTable.__table__

    value_to_update = connection.execute(table_to_update.select()\
        .where(table_to_update.c.scholarship_id == target.scholarship_id)).first()[-1]
    value_to_update -= 1
    connection.execute(table_to_update.update().where(table_to_update.c.scholarship_id == target.scholarship_id).values(rating = value_to_update))

#-----------------------------------------

if __name__ == '__main__':

    # ToDo Hide in env vars !!!
    engine = create_engine(os.environ.get('DATABASE_URL').replace('postgres', 'postgresql+psycopg2'))
    delete_schema(engine=engine)
    create_schema(engine=engine)

    