set -eu
BUILD_ROOT="${MEDIAFLOW_FFMPEG_BUILD_ROOT:?Set to a workspace containing sources/ffmpeg-9.0.2 and sources/lame-3.100}"
MEDIA_ARCH="$1"
MEDIA_PREFIX="$BUILD_ROOT/ffmpeg-$MEDIA_ARCH"
mkdir -p "$MEDIA_PREFIX" "$BUILD_ROOT/compile-$MEDIA_ARCH/lame" "$BUILD_ROOT/compile-$MEDIA_ARCH/ffmpeg"
cd "$BUILD_ROOT/compile-$MEDIA_ARCH/lame"
if test -f Makefile; then make distclean > clean.log 2>&1; fi
CFLAGS="-arch $MEDIA_ARCH -O2 -mmacosx-version-min=12.0" LDFLAGS="-arch $MEDIA_ARCH -mmacosx-version-min=12.0" "$BUILD_ROOT/sources/lame-3.100/configure" --prefix="$MEDIA_PREFIX" --disable-shared --enable-static --disable-frontend --disable-asm --disable-dependency-tracking > configure.log 2>&1
make -j6 > build.log 2>&1
make install > install.log 2>&1
cd "$BUILD_ROOT/compile-$MEDIA_ARCH/ffmpeg"
if test -f Makefile; then make distclean > clean.log 2>&1; fi
"$BUILD_ROOT/sources/ffmpeg-9.0.2/configure" --prefix=/opt/mediaflow --cc=clang --arch="$MEDIA_ARCH" --extra-cflags="-arch $MEDIA_ARCH -I../../ffmpeg-$MEDIA_ARCH/include -mmacosx-version-min=12.0" --extra-ldflags="-arch $MEDIA_ARCH -L../../ffmpeg-$MEDIA_ARCH/lib -mmacosx-version-min=12.0" --disable-autodetect --disable-doc --disable-debug --disable-x86asm --disable-ffplay --disable-ffprobe --disable-shared --enable-static --enable-libmp3lame --enable-securetransport --enable-zlib --disable-everything --enable-protocol=file,pipe,http,https,tcp,tls,crypto --enable-demuxer=mov,matroska,mp3,ogg,flac,wav,aac,hls,mpegts --enable-decoder=aac,aac_fixed,mp3,mp3float,opus,vorbis,flac,alac,pcm_s16le,pcm_s24le,pcm_f32le,mjpeg,png --enable-encoder=libmp3lame,aac,flac,mjpeg,png --enable-muxer=mp3,mp4,ipod,flac,ogg,matroska,mov,adts,wav --enable-parser=aac,aac_latm,mpegaudio,flac,opus,vorbis,h264,hevc,vp9,av1 --enable-bsf=aac_adtstoasc,extract_extradata,h264_mp4toannexb,hevc_mp4toannexb --enable-filter=anull,aresample,aformat,atrim,concat,volume,scale,format,null > configure.log 2>&1
make -j6 > build.log 2>&1
make install DESTDIR="$MEDIA_PREFIX/stage" > install.log 2>&1
mkdir -p "$MEDIA_PREFIX/bin"
cp "$MEDIA_PREFIX/stage/opt/mediaflow/bin/ffmpeg" "$MEDIA_PREFIX/bin/ffmpeg"
"$MEDIA_PREFIX/bin/ffmpeg" -version | head -3
