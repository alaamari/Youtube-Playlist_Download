import importlib.util
from pathlib import Path
import tempfile
import io
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
    def test_redirects_and_malformed_youtube_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as destination:
            for url in ['https://youtube.com/redirect?q=http://127.0.0.1', 'https://youtu.be/x', 'https://youtube.com/watch?v=cq5EnKIIpxk&v=00000000000', 'https://youtube.com/playlist?list=bad', 'https://youtube.com/watch?v=cq5EnKIIpxk#x']:
                with self.assertRaises(ValueError):runner.validate({'url':url,'format':'mp3','destination':destination})
            url,*_=runner.validate({'url':'https://youtu.be/cq5EnKIIpxk?si=tracking','format':'mp3','destination':destination})
            self.assertEqual(url,'https://www.youtube.com/watch?v=cq5EnKIIpxk')
    def test_supported_youtube_forms_remain_usable(self):
        for url in ['https://www.youtube.com/watch?v=cq5EnKIIpxk','https://youtube.com/shorts/cq5EnKIIpxk','https://music.youtube.com/watch?v=cq5EnKIIpxk','https://youtube.com/live/cq5EnKIIpxk','https://www.youtube.com/playlist?list=PL1234567890abcdef']:
            clean,provider,*_=runner.validate({'url':url,'format':'mp3','destination':'/tmp/chosen'})
            self.assertEqual(provider,'youtube');self.assertTrue(clean.startswith('https://www.youtube.com/'))
    def test_a_conversion_error_marks_a_download_with_saved_songs_partial(self):
        with tempfile.TemporaryDirectory() as destination:
            class Output:
                def __iter__(self):
                    (Path(destination)/'finished.mp3').write_bytes(b'finished')
                    yield 'Done\n'
                    yield 'FFmpegError: Failed to convert another song\n'
                def close(self):pass
            process=type('Process',(),{'stdout':Output(),'wait':lambda self:0})()
            with patch.object(runner.subprocess,'Popen',return_value=process),patch.object(runner,'emit') as emit:
                runner.main({'url':'https://open.spotify.com/album/3eZWAHSjyU30lfC89F2jnQ','format':'mp3','destination':destination,'data':destination})
            self.assertEqual(emit.call_args.kwargs['state'],'partial')


if __name__=='__main__':unittest.main()
