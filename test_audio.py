import pyglet
import sys


def play_audio(filename, loop=False):
    song = pyglet.media.load(filename)
    player = pyglet.media.Player()
    player.queue(song)
    if loop:
        player.eos_action = player.EOS_LOOP
    player.play()
    input('ENTER to stop')
    player.pause()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Provide filename!')
    else:
        play_audio(sys.argv[1])
