from datetime import datetime, timedelta
from flask import Flask, render_template
from math import sqrt
import functools
import os
import os.path


app = Flask(__name__)
app.config['BADGE_LOG_PATH'] = os.environ.get('BADGE_LOG_PATH', 'seclab.log')


def cache_from_file(fname):
    """Cache the value of a function until the desired file changes."""
    def wrapper(fn):
        # Store these in lists so inner can access them
        last_update = [-1]
        cached_value = [None]

        @functools.wraps(fn)
        def inner():
            file_mtime = os.path.getmtime(fname)
            if file_mtime > last_update[0]:
                with open(fname) as f:
                    cached_value[0] = fn(f)
                last_update[0] = file_mtime
            return cached_value[0]

        return inner
    return wrapper


def iter_ranges(logfile):
    """Yield each of the lab open-close ranges as start and stop datetimes."""
    current_start = None
    for line in logfile:
        date = datetime.strptime(line[:19], '%Y/%m/%d %H:%M:%S')
        if line[20:] == 'Received request: open\n':
            if current_start is None:
                current_start = date
        elif line[20:] == 'Received request: close\n':
            if current_start is not None:
                yield current_start, date
                current_start = None


def count_hours(logfile):
    """Return a list of the cumulative total for each hour in the week."""
    buckets = [0.0] * 24 * 7
    one_hour = timedelta(0, 60 * 60)

    first = None
    last = None

    for start, stop in iter_ranges(logfile):
        if first is None:
            first = start
        last = stop

        open_ref = datetime(start.year, start.month, start.day, start.hour)
        open_ref += one_hour
        open_ref = min(open_ref, stop)
        open_frac = (open_ref - start) / one_hour
        buckets[24 * start.weekday() + start.hour] += open_frac

        if start.date() != stop.date() or start.hour != stop.hour:
            stop_ref = datetime(stop.year, stop.month, stop.day, stop.hour)
            stop_frac = (stop - stop_ref) / one_hour
            buckets[24 * stop.weekday() + stop.hour] += stop_frac

        start_hour = 24 * open_ref.weekday() + open_ref.hour
        stop_hour = 24 * stop.weekday() + stop.hour
        if stop_hour < start_hour - 1:
            stop_hour += 24 * 7

        for hour in range(start_hour, stop_hour):
            buckets[hour % (24 * 7)] += 1

    return buckets, (last - first) / timedelta(7)


@cache_from_file(app.config['BADGE_LOG_PATH'])
def compute_timecard(logfile):
    """Compute the value and circle radius for each circle in the timecard.

    The logfile argument is inserted by cache_from_file, not the end caller.
    """
    data, num_weeks = count_hours(logfile)
    num_weeks -= 3
    print(num_weeks)

    # count_hours starts on Monday, but we want to start on Sunday
    data = data[-24:] + data[:-24]

    data = [d / num_weeks for d in data]
    max_hour = max(data)
    radii = [sqrt(h / max_hour) for h in data]

    return data, radii


@app.route('/timecard/')
def timecard_page():
    data, radii = compute_timecard()
    return render_template('timecard.html', data=data, radii=radii)


if __name__ == '__main__':
    app.run(debug=True)
