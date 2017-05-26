from flask import Flask, render_template, url_for, request, redirect, jsonify
app = Flask(__name__)

from sqlalchemy import create_engine, update, delete
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem

from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

engine = create_engine('sqlite:///restaurantmenu.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    print(login_session['state'])
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print ("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['credentials'] = credentials
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print ("done!")
    return output


@app.route('/restaurants/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/')
@app.route('/restaurant/')
def homeRestaurants():
	restaurants = session.query(Restaurant).all()
	items = session.query(MenuItem).all()
	return render_template('restaurants.html', restaurants=restaurants, items=items)


@app.route('/restaurant/new/', methods=['GET', 'POST'])
def addNewRestaurant():
	if request.method == 'POST':
		name = request.form['new-restaurant']
		session.add(Restaurant(name = name))
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		return render_template('newRestaurant.html')


@app.route('/restaurant/<int:restaurant_id>/edit/', methods=['GET', 'POST'])
def editRestaurant(restaurant_id):
	if request.method == 'POST':
		name = request.form['restaurant-edit-name']
		queryname = session.query(Restaurant).filter_by(id = restaurant_id).one()
		queryname.name = name
		session.add(queryname)
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		return render_template('editRestaurant.html', restaurant=restaurant)


@app.route('/restaurant/<int:restaurant_id>/delete/', methods=['GET', 'POST'])
def deleteRestaurant(restaurant_id):
	if request.method == 'POST':
		deleteRestaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		session.delete(deleteRestaurant)
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		return render_template('deleteRestaurant.html', restaurant=restaurant)


@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
def showMenu(restaurant_id):
	restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
	menu = session.query(MenuItem).filter_by(restaurant_id = restaurant_id)
	return render_template('menu.html', restaurant=restaurant, menu=menu)


@app.route('/restaurant/<int:restaurant_id>/new/', methods=['GET', 'POST'])
def newMenuItem(restaurant_id):
	if request.method == 'POST':
		name = request.form['item-name']
		price = request.form['item-price']
		description = request.form['item-description']
		course = request.form['course']

		session.add(Restaurant(name=name, price=price, description=description, course=course))
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		return render_template('newMenuItem.html', restaurant=restaurant)


@app.route('/restaurant/<int:restaurant_id>/menu/<int:item_id>/edit/', methods=['GET', 'POST'])
def editMenuItem(restaurant_id, item_id):
	if request.method == 'POST':
		name = request.form['item-name']
		price = request.form['item-price']
		description = request.form['item-description']
		course = request.form['course']

		query = session.query(MenuItem).filter_by(id = item_id).one()
		query.name = name
		query.price = price
		query.description = description
		query.course = course
		session.add(query)
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		item = session.query(MenuItem).filter_by(id = item_id).one()
		return render_template('editMenuItem.html', restaurant=restaurant, item=item)


@app.route('/restaurant/<int:restaurant_id>/menu/<int:item_id>/delete/', methods=['GET', 'POST'])
def deleteMenuItem(restaurant_id, item_id):
	if request.method == 'POST':
		deleteItem = session.query(MenuItem).filter_by(id = item_id).one()
		session.delete(deleteItem)
		session.commit()
		return redirect(url_for('homeRestaurants'))
	else:
		restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
		item = session.query(MenuItem).filter_by(id = item_id).one()
		return render_template('deleteMenuItem.html', restaurant=restaurant, item=item)


if __name__ == '__main__':
	app.secret_key = 'super_secret_key'
	app.debug = True
	app.run(host = '0.0.0.0', port = 5000)