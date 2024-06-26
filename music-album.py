# 根据图片和音乐合成带节奏的相册视频
import re
import threading
import traceback
import wave
from tkinter.ttk import Progressbar
from typing import Tuple, Union, Any

from common import gui
from common import python_box
import numpy as np
from progressbar import *
from skimage import transform
from beat_catch import beat_times

# pyinstaller import
from moviepy.audio.fx.audio_fadein import audio_fadein
from moviepy.audio.fx.audio_fadeout import audio_fadeout
from moviepy.audio.fx.audio_left_right import audio_left_right
from moviepy.audio.fx.audio_loop import audio_loop
from moviepy.audio.fx.audio_normalize import audio_normalize
from moviepy.audio.fx.volumex import volumex
from moviepy.video.fx.accel_decel import accel_decel
from moviepy.video.fx.blackwhite import blackwhite
from moviepy.video.fx.blink import blink
from moviepy.video.fx.colorx import colorx
from moviepy.video.fx.crop import crop
from moviepy.video.fx.even_size import even_size
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from moviepy.video.fx.freeze import freeze
from moviepy.video.fx.freeze_region import freeze_region
from moviepy.video.fx.gamma_corr import gamma_corr
from moviepy.video.fx.headblur import headblur
from moviepy.video.fx.invert_colors import invert_colors
from moviepy.video.fx.loop import loop
from moviepy.video.fx.lum_contrast import lum_contrast
from moviepy.video.fx.make_loopable import make_loopable
from moviepy.video.fx.margin import margin
from moviepy.video.fx.mask_and import mask_and
from moviepy.video.fx.mask_color import mask_color
from moviepy.video.fx.mask_or import mask_or
from moviepy.video.fx.mirror_x import mirror_x
from moviepy.video.fx.mirror_y import mirror_y
from moviepy.video.fx.painting import painting
from moviepy.video.fx.rotate import rotate
from moviepy.video.fx.scroll import scroll
from moviepy.video.fx.supersample import supersample
from moviepy.video.fx.time_mirror import time_mirror
from moviepy.video.fx.time_symmetrize import time_symmetrize
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.resize import resize
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.fx.speedx import speedx
from moviepy.video.VideoClip import ImageClip, ColorClip
import moviepy.audio.fx.all
import moviepy.editor



class FfmpegPlugin:
    def __init__(self):
        self.t = time.time()
        self.ffmpeg = "ffmpeg"

    def __del__(self):
        print("use time:", time.time() - self.t)

    def video2audio(self, directory):
        f_lst = python_box.dir_list(directory, "mp4$")
        for file in f_lst:
            wav = re.sub("mp4", "", file) + "wav"
            print(file, wav)
            cmd = "%s -y -i '%s' '%s'" % (self.ffmpeg, file, wav)
            print(cmd)
            os.system(cmd)

    def audio_split(self, directory):
        f_lst = python_box.dir_list(directory, "mp3$")
        for file in f_lst:
            seconds = 0
            while 1:
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                start = ("%01d:%02d:%02d" % (h, m, s))
                end = "0:0:07"
                seconds += 7
                print(file)
                mp4 = file
                mp4_split = re.sub(".mp3", "", file) + "_%d.pcm" % seconds
                cmd = "{ffmpeg} -y -ss {start} -t {end} -i {mp4} -acodec pcm_s16le -f s16le -ac 1 -ar 16000 {mp4_split}".format(
                    ffmpeg=self.ffmpeg, start=start, end=end, mp4_split=mp4_split, mp4=mp4)
                print(cmd)
                os.system(cmd)
                size = os.path.getsize(mp4_split)
                if size == 0:
                    break

    def video_split(self, file):
        mp4 = file
        mp4_split = re.sub(".mp4", "", file) + "_split.mp4"
        start = "0:0:9"
        end = "0:4:49"
        print(file)
        cmd = '''{ffmpeg} -y -ss {start} -t {end} -i "{mp4}" -vcodec copy -acodec copy "{mp4_split}"'''.format(
            ffmpeg=self.ffmpeg, start=start, end=end, mp4_split=mp4_split, mp4=mp4)
        print(cmd)
        os.system(cmd)

    def video_concat(self, dir):
        os.chdir(dir)
        f_lst = []
        for file in python_box.dir_list(dir, "mp4"):
            file = "file '{}'".format(file)
            f_lst.append(file)
        videoInfo = dir + "/videoInfo.txt"
        python_box.write_file(f_lst, videoInfo)
        cmd = '''{} -f concat -i {} -c copy {}output.mp4'''.format(self.ffmpeg, videoInfo, dir + "/")
        print(cmd)
        os.chdir(dir)
        os.system(cmd)
        os.remove(videoInfo)


def imageSequence(directory, target):
    # 只支持相同尺寸图片合成视频
    clip = moviepy.editor.ImageSequenceClip(directory, fps=10)
    clip.write_videofile(target)


def movie_concat(directory):  # 合并后衔接处卡顿重复
    outPath = directory + "/concatVideo.mp4"
    f_lst = python_box.dir_list(directory, "mp4")
    videoClips = []
    for file in f_lst:
        videoClip = moviepy.editor.VideoFileClip(file)
        videoClips.append(videoClip)
    videoClip = moviepy.editor.concatenate_videoclips(videoClips)
    videoClip.write_videofile(outPath)


def clip_speed_change(clip, speed, ta, tb):
    """
    调节速度
    keep change's time
    :param clip:
    :param speed:
    :param ta: 开始时间
    :param tb: 结束时间
    :return:
    """
    tb = ta + (tb - ta) * speed
    if tb <= clip.duration:
        speed_lambda = lambda c: speedx(c, speed)
        try:
            clip = clip.subfx(speed_lambda, ta, tb)
            # 此处报错关闭所有python即可解决,升级库
        except Exception as e:
            print(e)
    return clip


def num_speed(numpy_arr, n):
    new_numpy_arr = np.array([])
    for speed in numpy_arr:
        if speed > 1:
            new_speed = 1 + (speed - 1) * n
        else:
            if n <= 1:
                new_speed = (1 - (1 - speed) * n)
            if n > 1:
                new_speed = speed / n
        new_numpy_arr = np.append(new_numpy_arr, new_speed)
    return new_numpy_arr


def get_current_index(np_array: np.ndarray, value):
    """
    获取顺序排序数组中t附近的索引
    :param np_array:
    :param value:
    :return:
    """
    index = np.where(np_array <= value)
    if len(index) > 0:
        if len(index[0]) > 0:
            return index[0][len(index[0]) - 1]
    return len(np_array) - 1


def compute_time_line(np_time: np.ndarray, np_speed: np.ndarray, clips: list, audio_duration) -> list:
    """
    算法循环找出clip适合的时长，使总时长接近audio_duration
    :param np_time:
    :param np_speed:
    :param clips:
    :param audio_duration:
    :return: durations[]
    """
    default_var = audio_duration / len(clips)
    change_var = 0.01
    durations = []
    while range(1000000):
        durations.clear()
        for _ in clips:
            like_index = get_current_index(np_time, sum(durations))
            clip_duration = 1.0 / np_speed[like_index]
            clip_duration = clip_duration * default_var
            durations.append(clip_duration)
        total = sum(durations)
        if total > audio_duration:
            default_var *= 1 - change_var
        if total <= audio_duration:
            default_var *= 1 + change_var
        got = math.fabs(total - audio_duration) < 1
        if got:
            break
    if len(sys.argv) >= 3 and sys.argv[2] == "plot":
        from common import tools
        data = []
        for i in durations:
            data.append(1 / i)
        tools.plot_list(data)
    return durations


class MovieLib(FfmpegPlugin):
    def __init__(self):
        super().__init__()
        self.image_list = []
        self.audio_lst = []
        self.temp_audio_file = None
        self.out_video_file = None
        # 速度变化敏感度
        self.sens = 0.6
        # 视频适配无黑边
        self.adapt_full_view = False

    def set_adapt_full_view(self, adapt_full_view):
        self.adapt_full_view = adapt_full_view

    def set_out(self, directory):
        self.temp_audio_file = os.path.join(directory, "tmp.wav")
        self.out_video_file = os.path.join(directory, f"相册视频.mp4")

    def add_bgm(self, audio_file):
        if not audio_file:
            return
        self.audio_lst.append(audio_file)

    def add_pic(self, pic_dir):
        self.image_list.extend(sorted(python_box.dir_list(pic_dir, "jpg$", walk=True)))
        if not self.out_video_file:
            self.set_out(os.path.dirname(pic_dir))

    def audio2data(self, audio):
        """
        获取音频数据
        :param audio:
        :return:
        """
        f = wave.open(audio, 'rb')
        params = f.getparams()
        nchannels, sampwidth, self.framerate, nframes = params[:4]
        strData = f.readframes(nframes)
        f.close()
        waveData = np.fromstring(strData, dtype=np.short)
        waveData.shape = -1, 2
        waveData = waveData.T
        waveData = waveData[0]
        audioTime = np.arange(0, nframes) * (1.0 / self.framerate)
        if len(sys.argv) >= 3 and sys.argv[2] == "plot":
            from common import tools
            tools.plot_list(waveData, audioTime)
        np.abs(waveData, out=waveData)

        return audioTime, waveData

    def frame2speed(self, audioTime: list, wave_data: list, f_duration=None) -> Tuple[
        np.ndarray, Union[Union[float, int], Any]]:
        """
        根据帧获取音频速度
        :param f_duration:
        :param audioTime:
        :param wave_data:
        :return:
        """
        np_time = np.array([])
        np_speed = np.array([])
        # 获取关键帧
        f = 0
        if f_duration is None:
            f_duration = int(self.framerate * 0.5)
        while f <= len(audioTime) - 1:
            t = audioTime[f]
            speed = np.mean(wave_data[f:f + f_duration])
            f += f_duration
            np_time = np.append(np_time, t)
            np_speed = np.append(np_speed, speed)
        # 调整速度敏感度
        np_speed = np_speed / np.mean(np_speed)
        np_speed = np.where(np_speed >= 8, 8, np_speed)
        np_speed = np.where(np_speed <= 0.2, 0.2, np_speed)
        np_speed = np.where(np_speed >= 1, np_speed * self.sens, np_speed)
        np_speed = np.where(np_speed < 1, np_speed / self.sens, np_speed)
        np_speed = np_speed / np.mean(np_speed)
        return np_time, np_speed

    def resize_image_with_padding(self, image_clip, new_width, new_height):
        """
        设置照片尺寸 黑边补充
        :param image_clip:
        :param new_width:
        :param new_height:
        :return:
        """
        # Get the image array from ImageClip
        image = np.array(image_clip.get_frame(0))
        # Get the original image dimensions
        original_height, original_width = image.shape[:2]
        # Calculate the scale factor for resizing
        scale_factor_width = new_width / original_width
        scale_factor_height = new_height / original_height
        scale_factor = min(scale_factor_width, scale_factor_height)
        # Calculate the new dimensions after resizing
        adjusted_width = int(original_width * scale_factor)
        adjusted_height = int(original_height * scale_factor)
        # Resize the image using skimage.transform.resize
        resized_image = transform.resize(image, (adjusted_height, adjusted_width), mode='constant', anti_aliasing=True)
        # Create a new image with black background
        padded_image = np.zeros((new_height, new_width, 3), dtype=np.uint8)
        # Calculate the position to place the resized image
        start_x = (new_width - adjusted_width) // 2
        start_y = (new_height - adjusted_height) // 2
        # Place the resized image on the new image with black background
        padded_image[start_y:start_y + adjusted_height, start_x:start_x + adjusted_width] = (
                resized_image * 255).astype(np.uint8)
        # Convert the resulting NumPy array back to an ImageClip
        result_image_clip = ImageClip(padded_image)
        return result_image_clip

    def crop_clip(self, clip: moviepy.editor.ImageClip, width=1080 * 4 / 3, height=1080):
        """
        剪切图片
        :param clip:
        :param width:
        :param height:
        :return:
        """
        w, h = clip.size  # 视频长宽
        w_h = w / h

        if self.adapt_full_view:
            if w_h <= width / height:  # 宽度尺寸偏小
                clip = clip.resize(width=width)
                w, h = clip.size
                clip = clip.crop(x_center=w / 2, y_center=h / 2, width=width, height=height)
            else:
                clip = clip.resize(height=height)
                w, h = clip.size
                clip = clip.crop(x_center=w / 2, y_center=h / 2, width=width, height=height)
        else:
            return self.resize_image_with_padding(clip, int(width), int(height))

        return clip

    def generate_video(self, width=1080 * 4 / 3, height=1080):
        """
        图片直接生成变速视频
        跳过图片生成视频步骤
        :param width:
        :param height:
        :return:
        """
        # 生成音频数据
        if len(self.audio_lst) == 0:
            raise Exception("not exists any music")
        audio_clips = []
        for m in self.audio_lst:
            clip = moviepy.editor.AudioFileClip(m)
            audio_clips.append(clip)
        audio_clip = moviepy.editor.concatenate_audioclips(audio_clips)
        audio_clip.write_audiofile(self.temp_audio_file)
        audioTime, wave_data = self.audio2data(self.temp_audio_file)
        np_time, np_speed = self.frame2speed(audioTime, wave_data)
        time_line = compute_time_line(np_time, np_speed, self.image_list, audio_clip.duration)
        yield 1 / 4

        self.image_list.sort()
        image_clips = []
        for i in range(len(self.image_list)):
            yield 1 / 4 + i / len(self.image_list) * 1 / 2
            image_clip = moviepy.editor.ImageClip(self.image_list[i])
            image_clip = self.crop_clip(image_clip, width, height)
            image_clip.start = sum(time_line[0:i])
            image_clip.duration = time_line[i]
            image_clip.fps = 1
            image_clips.append(image_clip)

        video_clip = moviepy.editor.concatenate_videoclips(image_clips)
        video_clip.audio = audio_clip
        video_clip.write_videofile(self.out_video_file, fps=5)
        yield 1
        os.remove(self.temp_audio_file)
        return self.out_video_file

    def generate_video_from_beat(self, width=1080 * 4 / 3, height=1080):
        """
        根据librosa.beat库生成节奏相册视频
        :param width:
        :param height:
        :return:
        """
        # 生成音频数据
        if len(self.audio_lst) == 0:
            raise Exception("not exists any music")
        audio_clips = []
        for m in self.audio_lst:
            clip = moviepy.editor.AudioFileClip(m)
            audio_clips.append(clip)
        audio_clip = moviepy.editor.concatenate_audioclips(audio_clips)
        audio_clip.write_audiofile(self.temp_audio_file)
        time_line = beat_times(self.temp_audio_file)
        audio_clip.duration = time_line[-1]
        yield 1 / 4
        self.image_list.sort()
        image_clips = []
        # 设置图片时长
        for i in range(len(self.image_list)):
            yield 1 / 4 + i / len(self.image_list) * 1 / 2
            image_clip = moviepy.editor.ImageClip(self.image_list[i])
            if i + 1 > len(time_line) - 1:
                break
            image_clip = self.crop_clip(image_clip, width, height)
            image_clip.start = time_line[i]
            image_clip.duration = time_line[i + 1] - time_line[i]
            image_clip.fps = 1
            image_clips.append(image_clip)
        video_clip = moviepy.editor.concatenate_videoclips(image_clips)
        yield 3 / 4
        audio_clip.duration = video_clip.duration
        video_clip.audio = audio_clip
        video_clip.write_videofile(self.out_video_file, fps=5)
        yield 1
        os.remove(self.temp_audio_file)
        return self.out_video_file

    def run(self, mode=1):
        """
        批量图片合成clip
        通过bgm识别播放节奏，生成新的clip
        :param mode: 使用算法 1() 2()
        :return:
        """
        if mode == 1:
            return self.generate_video_from_beat()
        else:
            return self.generate_video()


def for_gen_code():
    gui.ComWin
    gui.select_dir
    gui.message


if __name__ == "__main__":
    """
    pic to video clip
    """
    movie_tool = MovieLib()
    # 图形界面处理
    win = gui.ComWin(title="电子视频相册")
    text = win.add_text("")
    text_change = lambda: text.config(
        text=f"音乐：{[os.path.basename(f) for f in movie_tool.audio_lst]}\n图片：{set(os.path.dirname(f) for f in movie_tool.image_list)}")
    win.add_buton("选择图片目录", lambda: (
        movie_tool.add_pic(gui.select_dir("选择图片所在位置目录")), text_change()
    ))
    win.add_buton("选择背景音乐", lambda: (
        movie_tool.add_bgm(gui.select_file("选择音乐文件")), text_change()
    ))
    mode = {'': 1}
    mode_button = win.add_buton(f"模式{mode['']}：{'节奏优先' if mode[''] == 1 else '时长对齐'}", lambda: (
        mode.__setitem__('', 2 if mode.get('') == 1 else 1),
        mode_button.config(text=f"模式{mode['']}：{'节奏优先' if mode[''] == 1 else '时长对齐'}")))
    adapt_button = win.add_buton(f"画幅：{'视频优先' if movie_tool.adapt_full_view else '照片优先'}", lambda: (
        movie_tool.set_adapt_full_view(not movie_tool.adapt_full_view),
        adapt_button.config(text=f"画幅：{'视频优先' if movie_tool.adapt_full_view else '照片优先'}")))


    def on_button_click():
        try:
            if len(movie_tool.image_list) == 0 or len(movie_tool.audio_lst) == 0:
                gui.message().showinfo(title="配置未完成", message=f"未配置图片和背景音乐")
                return
            progressbar = Progressbar(win.root)
            win.add_text(rf"生成中。。。")
            progressbar.pack()
            for i in movie_tool.run(mode.get('')):
                progressbar["value"] = i * 100
            win.add_text(rf"完成!生成视频在 {movie_tool.out_video_file}")
            gui.message().showinfo(title="完成", message=f"文件保存在：{movie_tool.out_video_file}")
        except Exception as e:
            traceback.print_exc()
            gui.message().showinfo(title="错误", message=e)
            win.add_text(rf"错误")


    win.add_buton("开始", lambda: (
        threading.Thread(target=on_button_click).start(),
    ))
