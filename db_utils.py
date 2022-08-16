from db import *
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import Session
from pdf_creator import generate_pdf

def add_new_user(user_id, session: Session):
    is_in_table = session.query(User).get(user_id)
    if is_in_table is None:
        user = User(user_id = user_id)
        session.add(user)
    
    session.commit()

def get_wishlist(user_id, start, quantity, session: Session):
    results = session.query(Wishlist).filter(Wishlist.user_id == user_id).order_by(desc(Wishlist.time_added)).limit(quantity).offset(start)
    
    short_data = []
    full_data = []

    for result in results:
        scholarship = session.query(ShortInfoTable).filter(ShortInfoTable.scholarship_id == result.scholarship_id).one()
        short_data.append(scholarship)
        scholarship = session.query(FullInfoTable).filter(FullInfoTable.scholarship_id == result.scholarship_id).one()
        full_data.append(scholarship)
    
    return (short_data, full_data)

def find_wishlist_results(user_id, session: Session):

    results = session.query(Wishlist).filter(Wishlist.user_id == user_id).all()

    return False if len(results) == 0 else True

def delete_from_wishlist(user_id, scholarship_id, session: Session):
    i = session.query(Wishlist).filter(Wishlist.user_id == user_id, Wishlist.scholarship_id == scholarship_id).one()
    session.delete(i)
    session.commit()


# ToDo complete sorting
def execute_search(country, sorting, ascending, start, quantity, session: Session):
    if country == 'Any country':
        if sorting == 'Popularity':
            if ascending:
                results = session.query(ShortInfoTable).order_by(ShortInfoTable.rating).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).order_by(desc(ShortInfoTable.rating)).limit(quantity).offset(start)
        elif sorting == 'Alphabetical':
            if ascending:
                results = session.query(ShortInfoTable).order_by(ShortInfoTable.title).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).order_by(desc(ShortInfoTable.title)).limit(quantity).offset(start)
        elif sorting == 'Deadline':
            if ascending:
                results = session.query(ShortInfoTable).order_by(ShortInfoTable.actual_deadline).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).order_by(desc(ShortInfoTable.actual_deadline)).limit(quantity).offset(start)
        else:
            None
    else:
        if sorting == 'Popularity':
            if ascending:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(ShortInfoTable.rating).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(desc(ShortInfoTable.rating)).limit(quantity).offset(start)
        elif sorting == 'Alphabetical':
            if ascending:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(ShortInfoTable.title).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(desc(ShortInfoTable.title)).limit(quantity).offset(start)
        elif sorting == 'Deadline':
            if ascending:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(ShortInfoTable.actual_deadline).limit(quantity).offset(start)
            else:
                results = session.query(ShortInfoTable).filter(ShortInfoTable.country == country).order_by(desc(ShortInfoTable.actual_deadline)).limit(quantity).offset(start)
        else:
            None

    return results

def find_previous_search_parameters(user_id, session: Session):

    results = session.query(LastSearchOption).filter(LastSearchOption.user_id == user_id).all()

    return (False, None) if len(results) == 0 else (True, results[0])

def get_country_list(session: Session):

    results = session.query(ShortInfoTable.country).distinct().all()
    
    return sorted([country_name[0] for country_name in results])

def update_search_options(user_id, country, sorting, order, session: Session):
    session.query(LastSearchOption).filter(LastSearchOption.user_id == user_id).delete(synchronize_session='fetch')
    session.commit()

    session.add(LastSearchOption(user_id = user_id,
                                country = country,
                                sorting = sorting,
                                ascending = True if order == 'Ascending' else False))
    session.commit()

def add_to_wishlist(user_id, scholarship_id, session: Session):

    result = session.query(Wishlist).filter(Wishlist.user_id == user_id, Wishlist.scholarship_id == scholarship_id)

    if result.count() == 0:
        session.add(Wishlist(user_id = user_id, scholarship_id = scholarship_id))
        session.commit()
        return True
    else:
        return False

def delete_from_wishlist(user_id, scholarship_id, session: Session):

    i = session.query(Wishlist).filter(Wishlist.scholarship_id == scholarship_id, Wishlist.user_id == user_id).one()
    session.delete(i)
    session.commit()

def get_full_data(scholarship_id, session: Session):

    full_info = session.query(FullInfoTable).filter(FullInfoTable.scholarship_id == scholarship_id).one()
    short_info = session.query(ShortInfoTable).filter(ShortInfoTable.scholarship_id == scholarship_id).one()
    return (short_info, full_info)

def generate_wishlist_pdf(user_id, session: Session):
    results = session.query(Wishlist.scholarship_id).filter(Wishlist.user_id == user_id).all()
    
    to_pdf = []

    for result in results:
        short_info: ShortInfoTable = session.query(ShortInfoTable).filter(ShortInfoTable.scholarship_id == result[0]).one()
        full_info: FullInfoTable = session.query(FullInfoTable).filter(FullInfoTable.scholarship_id == result[0]).one()
        to_pdf.append((short_info, full_info))
    
    return generate_pdf(to_pdf)

def get_links_to_channel(session: Session):
    return session.query(UsefulInfo.title, UsefulInfo.link).all()

def delete_user_data_from_db(user_id, session: Session):
    session.query(LastSearchOption).filter(LastSearchOption.user_id == user_id).delete()
    session.query(Wishlist).filter(Wishlist.user_id == user_id).delete()
    session.query(User).filter(User.user_id == user_id).delete()
    session.commit()

def get_scholarship_by_id(scholarship_id, session: Session):
    result = session.query(ShortInfoTable).filter(ShortInfoTable.scholarship_id == scholarship_id).one()
    return result


if __name__ == '__main__':
    print('None')
    # ToDo Hide it
    #engine = create_engine(os.environ.get('DATABASE_URL))
    #session = Session(bind=engine)

    #add_new_user(12345, session=session)
    #execute_search(' UK', 0, 10, session=session)
    #print(find_previous_search_parameters(user_id= 406910278, session=session))
    #print(get_country_list(session))
    #update_search_options(12345, 'UK', 'Popularity', 'Descending', session)
    #add_to_wishlist(12345, 5868, session=session)
    #add_to_wishlist(12345, 5868, session=session)
    #delete_from_wishlist(12345, 5868, session=session)
    #print(get_full_data(2776, session=session).scholarship_id)
    #generate_wishlist_pdf(406910278, session=session)
    #get_links_to_channel(session=session)