#!/usr/bin/env python
"""
Run script for Mario Trader Bot
"""
import os
import sys
import argparse
from main import main as main_func


def run():
    """
    Run the bot with the specified command
    """
    parser = argparse.ArgumentParser(description='Run Mario Trader Bot')
    parser.add_argument('command', choices=['start', 'start-multi', 'login', 'info', 'test', 'list-pairs'],
                        help='Command to run')
    parser.add_argument('--login', type=int, help='MT5 account login')
    parser.add_argument('--password', type=str, help='MT5 account password')
    parser.add_argument('--server', type=str, help='MT5 server name')
    parser.add_argument('--pair', type=str, help='Currency pair to trade')
    parser.add_argument('--interval', type=int, default=60, 
                        help='Interval between trades in seconds (for multi-pair mode)')
    parser.add_argument('--pairs', action='store_true', help='Display available currency pairs (with info command)')
    
    args = parser.parse_args()
    
    # Prepare sys.argv for main.py
    if args.command == 'start-multi':
        sys.argv = ['main.py', 'start', '--multi']
        if args.login:
            sys.argv.extend(['--login', str(args.login)])
        if args.password:
            sys.argv.extend(['--password', args.password])
        if args.server:
            sys.argv.extend(['--server', args.server])
        if args.interval:
            sys.argv.extend(['--interval', str(args.interval)])
    elif args.command == 'list-pairs':
        sys.argv = ['main.py', 'list-pairs']
    elif args.command == 'info' and args.pairs:
        sys.argv = ['main.py', 'info', '--pairs']
    elif args.command == 'test':
        # Run the test script
        import unittest
        from test_bot import TestCurrencyPairs, TestIndicators, TestSignalGeneration
        
        # Create a test loader
        loader = unittest.TestLoader()
        
        # Create a test suite
        suite = unittest.TestSuite()
        suite.addTest(loader.loadTestsFromTestCase(TestCurrencyPairs))
        suite.addTest(loader.loadTestsFromTestCase(TestIndicators))
        suite.addTest(loader.loadTestsFromTestCase(TestSignalGeneration))
        
        # Run the tests
        runner = unittest.TextTestRunner()
        result = runner.run(suite)
        
        return 0 if result.wasSuccessful() else 1
    else:
        sys.argv = ['main.py', args.command]
        if args.login:
            sys.argv.extend(['--login', str(args.login)])
        if args.password:
            sys.argv.extend(['--password', args.password])
        if args.server:
            sys.argv.extend(['--server', args.server])
        if args.pair:
            sys.argv.extend(['--pair', args.pair])
    
    # Run the main function
    if args.command != 'test':
        return main_func()
    
    return 0


if __name__ == '__main__':
    sys.exit(run()) 