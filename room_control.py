#!/usr/bin/env python3

# Jari Torniainen <jari.torniainen@ttl.fi>,
# Finnish Institute of Occupational Health
# Copyright 2015
#
# This code is released under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Please see the file LICENSE for details

import curses
import time
from configparser import ConfigParser
from collections import OrderedDict
import pyglet
import phue

# TODO: Session sequences should be reset after a succesful run
# TODO: Add docstrings


class Sequence(object):
    def __init__(self, name, config, bridge):
        self.name = name
        if 'hue' in config:
            self.hue = int(config['hue'])
        else:
            self.hue = 0  # Or whatever corresponds to white

        if 'bri' in config:
            self.bri = int(config['bri'])
        else:
            self.bri = 10

        if 'audio' in config:
            self.audio = config['audio']
        else:
            self.audio = None

        if 'audio_loop' in config:
            self.audio_loop = eval(config['audio_loop'])
        else:
            self.audio_loop = False

        if 'duration' in config:
            self.duration = float(config['duration'])
        else:
            self.duration = 60

        self.bridge = bridge

        self.running = False
        self.started = False
        self.run_started = None
        self.remaining = self.duration
        self.finished = False

        # Preload audio
        # TODO: check if this is the most efficient way of doing this. Right now
        #       we create one player object per sequence. We could, instead,
        #       have one player and change the queued song.

        if self.audio:
            self.player = pyglet.media.Player()
            self.player.queue(pyglet.media.load(self.audio))
            if self.audio_loop:
                self.player.eos_action = self.player.EOS_LOOP

    def start(self):
        self.running = True
        self.started = True
        self.run_started = time.time()
        if self.bridge:
            self.start_hue()
        if self.audio:
            self.play_audio()

    def update(self):
        self.remaining = self.duration - (time.time() - self.run_started)

        if self.remaining <= 0:
            self.remaining = 0
            self.running = False
            self.finished = True
            if self.audio:
                self.stop_audio()
            if self.bridge:
                self.bridge.set_group('all', 'on', False)

    def play_audio(self, loop=False):
        self.player.play()

    def stop_audio(self):
        self.player.pause()

    def start_hue(self):
        self.bridge.set_group('all', 'on', True)
        self.bridge.set_group('all', 'bri', self.bri)
        self.bridge.set_group('all', 'hue', self.hue)


class Session(object):
    """ Container for session information. """

    def __init__(self, name=None, configuration_file=None, log_file=None,
                 bridge_ip=None):
        self.name = name
        self.configuration_file = configuration_file
        self.sequences = []
        if log_file:
            self.log_file = log_file
        elif name:
            self.log_file = name + '.log'
        else:
            self.log_file = None

        # Set up hue lights
        if bridge_ip:
            self.bridge = phue.Bridge(bridge_ip)
            self.bridge.create_group('all', [1, 2, 3, 4, 5, 6, 7, 8, 9])
            self.bridge.set_group('all', 'on', False)
        else:
            self.bridge = None

    def set_name(self, session_name):
        self.name = session_name
        self.log_file = session_name + '.log'

    def set_configuration_file(self, configuration_file):
        self.configuration_file = configuration_file

    def load_configuration(self):
        # TODO This needs a check whether the file exists or not
        self.sequences = read_config(self.configuration_file, self.bridge)


def read_config(filename, bridge):
    cfg = ConfigParser()
    cfg.read(filename)
    cfg = OrderedDict(cfg)

    if 'DEFAULT' in cfg.keys():
        cfg.pop('DEFAULT')

    sequences = []
    for sequence in cfg.keys():
        sequences.append(Sequence(sequence, dict(cfg[sequence]), bridge))
    return sequences


def popup(scr, message_string):
    scr.clear()
    scr.border(0)
    scr.addstr(1, 1, message_string)
    scr.refresh()
    scr.getch()


def get_input(scr, prompt_string):
    scr.clear()
    scr.border(0)
    scr.addstr(2, 2, prompt_string)
    scr.refresh()
    return scr.getstr(10, 10, 60)


def create_session(session_name, configuration_file):
    bridge_ip = '192.168.2.252'
    session = Session(session_name, configuration_file, bridge_ip=bridge_ip)
    session.load_configuration()
    return session


def start_session(scr):
    while True:
        curses.curs_set(1)
        scr.clear()
        scr.addstr(0, 0, 'START NEW SESSION')
        scr.addstr(1, 0, 'Enter session name:', curses.A_BOLD)
        curses.echo()
        session_name = scr.getstr(1, 20, 21).decode(encoding='utf-8')
        scr.addstr(2, 0, 'Enter configuration file location:', curses.A_BOLD)
        configuration_file = scr.getstr(2, 35, 20).decode(encoding='utf-8')
        scr.addstr(3, 0, 'Is this correct [y/n]?')
        curses.curs_set(0)
        curses.noecho()
        confirmation = scr.getch()
        if confirmation == ord('y') or confirmation == ord('Y'):
            # Check if configuration file is valid
            session = create_session(session_name, configuration_file)
            return session, 0


def run_sequences(scr, session, sequences):

    # TODO: These two should be defined somewhere else
    MAX_BAR_LENGTH = 60

    # Start run
    running = True
    current_sequence = 0
    sequences[0].start()

    while running:
        scr.clear()
        scr.border(0)

        # Draw all sequences
        text_start = 2
        for idx, sequence in enumerate(sequences):
            if idx == current_sequence and not sequence.finished:
                if sequence.started:
                    sequence.update()
                else:
                    sequence.start()
                    with open(session.log_file, 'a') as f:
                        f.write('[{}] Sequence "{}" started'.format(time.ctime(), sequence.name))

                bar_len = round((sequence.remaining / sequence.duration) *
                                MAX_BAR_LENGTH)
                sequence_text = '%s [Remaining: %0.2f]' % (sequence.name,
                                                           sequence.remaining)
                scr.addstr(text_start + idx * 2, 5, sequence_text)
                scr.addstr(text_start + idx * 2 + 1, 5, ' ' * bar_len,
                           curses.color_pair(1))
                if sequence.finished:
                    with open(session.log_file, 'a') as f:
                        f.write('[{}] Sequence "{}" finished'.format(time.ctime(), sequence.name))
                    current_sequence += 1

            elif idx == current_sequence and sequence.finished:
                sequence_text = '%s [Finished]' % (sequence.name)
                scr.addstr(text_start + idx * 2, 5, sequence_text)
                if current_sequence == len(sequences) - 1:
                    running = False
                else:
                    current_sequence += 1

            elif sequence.finished:
                sequence_text = '%s [Finished]' % (sequence.name)
                scr.addstr(text_start + idx * 2, 5, sequence_text)
            else:
                sequence_text = '%s [Not started]' % (sequence.name)
                scr.addstr(text_start + idx * 2, 5, sequence_text)
                scr.addstr(text_start + idx * 2 + 1, 5, ' ' * MAX_BAR_LENGTH,
                           curses.color_pair(1))

        if sequences[-1].finished:
            running = False

        scr.refresh()
        time.sleep(.1)


def run_session(scr, session):
    # Check is there a valid session?
    if not session.sequences:
        popup(scr, 'No sequence(s) found in current session! [Enter]')
    else:
        with open(session.log_file, 'w') as f:
            f.write('[{}] Session started'.format(time.ctime()))
        run_sequences(scr, session, session.sequences)
        popup(scr, 'Session finished! [ENTER to exit]')
    return 0


def main_menu(scr, session):
    start_y_menu = 5
    start_y_info = 1
    start_x = 1
    menu_items = ['Start new session', 'Run Session', 'Exit']
    info_items = {'Session name': session.name,
                  'Configuration file': session.configuration_file,
                  'Log file': session.log_file,
                  'Bridge IP': session.bridge_ip}
    info_items = OrderedDict(info_items)

    for idx, item in enumerate(menu_items):
        scr.addstr(start_y_menu + idx, start_x, str(idx + 1) + '. ',
                   curses.A_BOLD)
        scr.addstr(start_y_menu + idx, start_x + 4, item)

    for idx, item in enumerate(info_items.keys()):
        value = info_items[item]
        if not value:
            value = str(value)
        scr.addstr(start_y_info + idx, start_x, item, curses.A_BOLD)
        scr.addstr(start_y_info + idx, start_x + len(item) + 1, value)

    user_input = scr.getch()
    if user_input == ord('1'):
        return 10
    elif user_input == ord('2'):
        return 20
    elif user_input == ord('3'):
        return 99
    else:
        return 0


def main(scr):
    state = 0
    is_running = True

    session = Session()

    STATE_MENU = 0
    STATE_START_NEW_SESSION = 10
    STATE_SESSION_RUNNING = 20
    STATE_SESSION_FINISHED = 30
    STATE_EXIT = 99

    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_CYAN)
    curses.curs_set(0)

    while is_running:
        scr.clear()
        scr.border(0)

        if state == STATE_MENU:
            state = main_menu(scr, session)
        elif state == STATE_START_NEW_SESSION:
            session, state = start_session(scr)
        elif state == STATE_SESSION_RUNNING:
            state = run_session(scr, session)
        elif state == STATE_SESSION_FINISHED:
            pass
        elif state == STATE_EXIT:
            is_running = False

        scr.refresh()


if __name__ == '__main__':
    curses.wrapper(main)
