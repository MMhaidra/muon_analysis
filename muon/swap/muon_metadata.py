
from swap.db import DB

import argparse
import csv
import json
import re

import logging
logger = logging.getLogger(__name__)

parse = re.compile('run([0-9]+)_evt([0-9]+).jpeg')


def options(parser):
    parser.add_argument('file', help='subject csv dump')


def run(args):
    fname = args.file[0]
    data = get_metadata(fname)
    upload_data(data)


def upload_data(data):
    db = DB()
    requests = []

    def write():
        nonlocal requests
        if len(requests) > 0:
            db.subjects.bulk_write(requests)
            requests = []

    for subject, metadata in data.items():
        r = db.subjects.update_metadata(subject, metadata, False)
        requests.append(r)

        if len(requests) > 1e4:
            write()
    write()


def get_metadata(fname):
    data = {}

    with open(fname, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            subject, metadata = parse_row(row)
            data[subject] = metadata

    return data


def parse_row(row):
    meta = json.loads(row['metadata'])

    subject = row['subject_id']
    fname = meta['Filename']

    run_, evt = parse_fname(fname)

    metadata = {
        'run': run_,
        'event': evt,
    }

    return subject, metadata


def parse_fname(fname):
    run_, evt = parse.match(fname).groups()
    return run_, evt


def main():
    parser = argparse.ArgumentParser()
    options(parser)
    args = parser.parse_args()
    run(args)


if __name__ == '__main__':
    main()
