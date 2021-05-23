from flask import make_response, jsonify, session


def misc_error(my_function):
    def wrap(*args, **kwargs):
        try:
            return my_function(*args, **kwargs)
        except Exception as e:
            print(str(e))
            return make_response(jsonify({
                'error': 'An unexpected error has occurred. Please try again later.'
            }), 400)

    wrap.__name__ = my_function.__name__
    return wrap


def login_required(my_function):
    def wrap(*args, **kwargs):
        if 'user' not in session.keys():
            return make_response(jsonify({
                'error': 'You are not logged in.'
            }), 400)

        else:
            return my_function(*args, **kwargs)

    wrap.__name__ = my_function.__name__
    return wrap
