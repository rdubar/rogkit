#!/usr/bin/env python3
import argparse

def process_arguments():
    parser = argparse.ArgumentParser(description='Process arguments')

    # Database management options
    parser.add_argument('--update', action='store_true', help='Update database')
    parser.add_argument('-R', '--reset', action='store_true', help='Reset database')
    parser.add_argument('-D', '--duplicates', action='store_true', help='Remove duplicates')

    # Display options
    parser.add_argument('-a', '--all', action='store_true', help='Show all records')
    parser.add_argument('-d', '--dvd', action='store_true', help='Show uncompressed DVDs')
    parser.add_argument('-l', '--latest', action='store_true', help='Show latest additions')
    parser.add_argument('-s', '--summary', action='store_true', help='Show a summary for each title')
    parser.add_argument('-n', '--number', type=int, default=10, help='Number of results to return')
    parser.add_argument('-r', '--resolution', action='store_true', help='Sort by resolution')
    parser.add_argument('-y', '--year', action='store_true', help='Sort by year of release') 

    # Mode options
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    parser.add_argument('--schema', action='store_true', help='Update database schema')

    args, search_terms = parser.parse_known_args()
    return args, ' '.join(search_terms)



