from datetime import datetime, timedelta
from flask import Flask, Response, request, render_template
from math import sqrt
import functools
import os
import os.path


app = Flask(__name__)
app.config['BADGE_LOG_PATH'] = os.environ.get('BADGE_LOG_PATH', 'seclab.log')


def file_memoize(fname):
    """Cache the value of a function until the desired file changes."""
    def wrapper(fn):
        # Store these in lists so inner can access them
        last_update = {}
        cached_values = {}

        @functools.wraps(fn)
        def inner(*args):
            file_mtime = os.path.getmtime(fname)
            if args not in cached_values or file_mtime > last_update[args]:
                with open(fname) as f:
                    cached_values[args] = fn(f, *args)
                last_update[args] = file_mtime
            return cached_values[args]

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


def count_hours(ranges, range_start=None, range_stop=None):
    """Return a list of the cumulative total for each hour in the week."""
    buckets = [0.0] * (24 * 7)
    one_hour = timedelta(0, 60 * 60)

    first = None
    last = None

    for start, stop in ranges:
        if ((range_start is not None and start < range_start) or
                (range_stop is not None and stop > range_stop)):
            continue

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

    return buckets, first, last


def count_total_hours(start, stop):
    """Count the number of times each hour slot has occurred."""
    if start is None or stop is None:
        return [0] * (24 * 7)

    start_hour = 24 * start.weekday() + start.hour
    stop_hour = 24 * stop.weekday() + stop.hour
    num_weeks = (stop - start).days // 7
    overlap_offset = (stop_hour - start_hour + 1) % (24 * 7) - 1
    totals = []
    for hour in range(24 * 7):
        total = num_weeks
        if (hour - start_hour) % (24 * 7) <= overlap_offset:
            total += 1
        totals.append(total)
    return totals


@file_memoize(app.config['BADGE_LOG_PATH'])
def compute_timecard(logfile, range_start, range_stop):
    """Compute the value and circle radius for each circle in the timecard.

    The logfile argument is inserted by cache_from_file, not the end caller.
    """
    ranges = iter_ranges(logfile)
    counts, first, last = count_hours(ranges, range_start, range_stop)
    totals = count_total_hours(first, last)

    # datetime's weekday=0 starts on Monday, but we want to start on Sunday
    counts = counts[-24:] + counts[:-24]
    totals = totals[-24:] + totals[:-24]

    percents = [(c / t if t else 0) for c, t in zip(counts, totals)]
    max_count = max(counts) or 1
    radii = [sqrt(c / max_count) for c in counts]

    return percents, radii


def get_date_or_none(obj, key):
    """If obj contains key and its value is a valid date, return the date.

    Otherwise, return None.
    """
    try:
        return datetime.strptime(obj[key], '%Y-%m-%d')
    except (KeyError, ValueError):
        return None


@app.route('/timecard.svg')
def timecard_page():
    range_start = get_date_or_none(request.args, 'start')
    range_stop = get_date_or_none(request.args, 'end')
    data, radii = compute_timecard(range_start, range_stop)
    contents = render_template('timecard.svg', data=data, radii=radii)
    return Response(contents, mimetype='image/svg+xml')


if __name__ == '__main__':
    app.run(debug=True)
