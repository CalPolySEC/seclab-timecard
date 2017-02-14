from flask import Flask, render_template


app = Flask(__name__)


@app.route('/timecard/')
def timecard_page():
    return render_template('timecard.html')


if __name__ == '__main__':
    app.run(debug=True)
