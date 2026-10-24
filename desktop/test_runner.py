import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('desktop_runner',ROOT/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class PortableCommands(unittest.TestCase):
    def test_frozen_spotify_uses_bundled_dispatch_and_artist_source_priority(self):
        with patch.object(runner.sys,'frozen',True,create=True):
            cmd=runner.spotify_command('https://open.spotify.com/album/3eZWAHSjyU30lfC89F2jnQ','mp3',Path('/tmp/files'),Path('/tmp/data'))
        self.assertEqual(cmd[1:3],['--spotdl','/tmp/data/tool-home'])
        self.assertNotIn('-c',cmd);self.assertIn('{track-number}',cmd[-1])
        self.assertEqual(cmd[cmd.index('--audio')+1:cmd.index('--audio')+3],['bandcamp','youtube-music'])
    def test_frozen_youtube_has_no_dependency_on_a_python_interpreter(self):
        with patch.object(runner.sys,'frozen',True,create=True):
            for fmt in ('mp3','m4a','flac','mp4'):
                cmd=runner.youtube_command('https://youtu.be/fixture',fmt,Path('/tmp/files'),False)
                self.assertEqual(cmd[1],'--yt-dlp');self.assertNotIn('-m',cmd)
                self.assertIn('--no-playlist',cmd);self.assertEqual(cmd[-2:],['--','https://youtu.be/fixture'])
    def test_bad_source_and_spotify_video_are_rejected(self):
        with tempfile.TemporaryDirectory() as destination:
            for url,fmt in [('https://evil.example/x','mp3'),('https://open.spotify.com/album/3eZWAHSjyU30lfC89F2jnQ','mp4')]:
                with self.assertRaises(ValueError):runner.validate({'url':url,'format':fmt,'destination':destination})


if __name__=='__main__':unittest.main()
