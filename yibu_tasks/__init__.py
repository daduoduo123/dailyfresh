import os
import threading
import time
import wave
import datetime
import xlwt
import pyaudio
from framework.logger import Log
from framework.exception import InvalidParaException
from framework.dft import DftException, DftCode, ErrorCode
from framework.utils import get_resource_path
from devicetest.log.variables import VAR
from xlutils.copy import copy
from xlrd import open_workbook


class AresMaya(object):
    # 量化位数（byte）
    DEFAULT_CHUNK = 1024
    # 取样值的量化格式
    DEFAULT_FORMAT = pyaudio.paInt16
    # 通道数
    DEFAULT_CHANNELS = 1
    # 采样频率
    DEFAULT_RATE = 8000
    # 默认mos分
    BACK_DEFAULT_VALUE = '0.123'   
    # 默认输入通道12
    DEFAULT_INPUT_CHANNEL12 = 'ch12'
    # 默认输入通道34
    DEFAULT_INPUT_CHANNEL34 = 'ch34'
    # 默认输出通道12
    DEFAULT_OUTPUT_CHANNEL12 = 'ch12'
    # 默认输入通道34
    DEFAULT_OUTPUT_CHANNEL34 = 'ch34'
    # PESQ算法
    VQM_PESQ_ALGORITHM = "PESQ"
    # POLQA算法
    VQM_POLQA_ALGORITHM = "POLQA"
    
    def __init__(self, maya_id=1):
        """
            maya_id: maya声卡设备硬件标识
        """
        self.TAG = self.__class__.__name__
        # 录音标识
        self.v_record_flag_dict = {}  
        # 播放标识
        self.v_play_flag_dict = {}  
        self.maya_id = maya_id
        self.v_mos_flag_dict = False
        self.pyaudio = pyaudio.PyAudio()
        self.mos_li = []
        self.avg_mos = 0
        self.smallest_mos = 0
        self.biggest_mos = 0
        self.case_name = VAR.CurCase.Name
        self.node_time = 0

    def get_report_path(self):
        # 报告路径
        report_recent_dir = VAR.Project.ReportDir
        return report_recent_dir    
    
    def ex_start_sample(self, channel_id, audio_name):
        """
                            开始录音
        """
        # 录音文件存储处理
        time_str = time.strftime("%Y%m%d%H%M%S")
        Log.i(self.TAG, 'channel_id:%s,maya_id:%s,time_str:%s,audio_name:%s' % (channel_id, self.maya_id, time_str, audio_name))
        audio_name = os.path.basename(audio_name).split('.')[0] + '_' + str(self.maya_id) + '_' + channel_id + '_' + time_str + '.wav'
        save_path = os.path.join(self.get_report_path(), "Record")
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        time_stap = time.strftime("%Y%m%d%H%M%S")
        record_name = audio_name.split('.')[0]
        save_filepath = os.path.join(save_path, '%s_%s.wav' % (record_name, time_stap))
        Log.i(self.TAG, 'save_filepath:%s' % save_filepath)
        # 播放和录音要同时操作，用线程启动录音任务
        self.__aresaw_maya_read_audio(channel_id, save_filepath)
        return save_filepath

    def __aw_maya_start_sample(self, channel_id, audio_name):
        """
                            开始录音
        """
        # 录音文件存储处理
        time_str = time.strftime("%Y%m%d%H%M%S")
        Log.i(self.TAG, 'channel_id:%s,maya_id:%s,time_str:%s,audio_name:%s' % (channel_id, self.maya_id, time_str, audio_name))
        audio_name = os.path.basename(audio_name).split('.')[0] + '_' + str(self.maya_id) + '_' + channel_id + '_' + time_str + '.wav'
        save_path = os.path.join(r'\\?', self.get_report_path(), "Record", self.case_name)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        time_stap = time.strftime("%Y%m%d%H%M%S")
        record_name = audio_name.split('.')[0]
        save_filepath = os.path.join(save_path, '%s_%s.wav' % (record_name, time_stap))
        Log.i(self.TAG, 'save_filepath:%s' % save_filepath)
        # 播放和录音要同时操作，用线程启动录音任务
        self.__aresaw_maya_read_audio(channel_id, save_filepath)
        return save_filepath

    def __aw_maya_stop_sample(self, channel_id='ch12'):
        """
                            停止录音
        """
        k = self.__aresaw_maya_key(channel_id)
        self.v_record_flag_dict[k] = False
        

    def __aw_maya_start_play(self, audio_name, channel_id='ch12'):
        """
                            线程启动播放任务，实现stream的创建，wave的读出
        """
        th = threading.Thread(target=self.__aresaw_maya_play_audio,
                              args=(audio_name, channel_id))
        th.setDaemon(True)
        th.start()
        
    def start_back_mos_value_th(self, play_line, record_line, algorithm, play_file, timeout_seconds=15, deal_mos=True):
        """
                            线程启动start_back_mos_value,
        """
        th = threading.Thread(target=self.start_back_mos_value,
                              args=(play_line, record_line, algorithm, play_file, timeout_seconds, deal_mos))
        th.setDaemon(True)
        th.start()
        return th
        
    def __aw_maya_stop_play(self, channel_id='ch12'):
        """
                            停止播放
        """
        k = self.__aresaw_maya_key(channel_id)
        self.v_play_flag_dict[k] = 'stop'

    def __aw_maya_pause_play(self, channel_id='ch12'):
        """
                            暂停播放
        """
        k = self.__aresaw_maya_key(channel_id)
        self.v_play_flag_dict[k] = 'pause'

    def __aw_maya_continue_play(self, channel_id='ch12'):
        """
                            继续播放
        """
        k = self.__aresaw_maya_key(channel_id)
        self.v_play_flag_dict[k] = 'start'

    def __aresaw_maya_getname(self, channel_id):
        """
                            通过插入通道ID，匹配实际声卡可用输入输出通道
        """
        if channel_id == 'ch12':
            name = 'MAYA44USB Ch12 (MAYA44USB Audio'
        elif channel_id == 'ch34':
            name = 'MAYA44USB Ch34 (MAYA44USB Audio'
        else:
            raise InvalidParaException(channel_id, 'input channel para error,please fill channel value again')
        return name.lower().replace(' ', '')

    def __aresaw_maya_key(self, channel_id):
        """
                            根据传入通道，取key
        """
        return str(self.maya_id) + '_' + str(channel_id)

    def __aresaw_maya_open_record_audio(self, channel_id):
        """"
                                生成录制所需的record_pyaudio_obj, record_stream_obj对象
        """
        record_stream_obj = None
        record_pyaudio_obj = pyaudio.PyAudio()
        maya_name = self.__aresaw_maya_getname(channel_id)
        for index in range(record_pyaudio_obj.get_device_count()):
            info = record_pyaudio_obj.get_device_info_by_index(index)
            host_api = info.get('hostApi')
            cid = info.get('maxInputChannels')
            cname = info.get('name').lower().replace(' ', '')
            
            if cid != 0 and maya_name in cname and host_api == 0:
                try:
                    record_stream_obj = record_pyaudio_obj.open(format=self.DEFAULT_FORMAT,
                                                                  channels=self.DEFAULT_CHANNELS,
                                                                  rate=self.DEFAULT_RATE,
                                                                  input=True,
                                                                  input_device_index=info['index'],
                                                                  frames_per_buffer=self.DEFAULT_CHUNK)
                    break
                except Exception:
                    Log.e(self.TAG, 'this channel is used')
                    self.__realse(channel_id)
            time.sleep(0.1)
        Log.i(self.TAG, 'record_pyaudio_obj:%s,record_stream_obj:%s' % (record_pyaudio_obj, record_stream_obj))
        return record_pyaudio_obj, record_stream_obj
        
    def __aresaw_maya_thread_read_audio(self, channel_id, save_filepath):
        """
                          使用record_stream_obj对象进行文件录制
        """
        k = self.__aresaw_maya_key(channel_id)
        record_pyaudio_obj, record_stream_obj = self.__aresaw_maya_open_record_audio(channel_id)
        if not record_stream_obj:
            Log.i(self.TAG, 'no record_stream_obj')
            return None
        self.v_record_flag_dict[k] = True
        try:
            write_wf = wave.open(save_filepath, 'wb')
            write_wf.setnchannels(self.DEFAULT_CHANNELS)
            write_wf.setsampwidth(record_pyaudio_obj.get_sample_size(self.DEFAULT_FORMAT))
            write_wf.setframerate(self.DEFAULT_RATE)
            while self.v_record_flag_dict.get(k):
                data = record_stream_obj.read(self.DEFAULT_CHUNK)
                write_wf.writeframes(data)
            # 停止录制后，需顺序关闭该资源
        finally:
            record_stream_obj.stop_stream()
            record_stream_obj.close()
            record_pyaudio_obj.terminate()
            write_wf.close()

    def __aresaw_maya_read_audio(self, channel_id, save_filepath):
        th = threading.Thread(target=self.__aresaw_maya_thread_read_audio,
                              args=(channel_id, save_filepath))
        th.setDaemon(True)
        th.start()

    def __aresaw_maya_open_play_audio(self, file_path, channel_id):
        """"
                                生成录制所需的play_stream_obj, play_wf, play_pyaudio_obj对象
        """
        play_stream_obj = None
        play_pyaudio_obj = pyaudio.PyAudio()
        play_wf = wave.open(file_path, 'rb')
        for index in range(play_pyaudio_obj.get_device_count()):
            info = play_pyaudio_obj.get_device_info_by_index(index)
            value = info.get('maxOutputChannels')
            name = info.get('name')
            host_api = info.get('hostApi')
            if value != 0 and host_api == 0 and channel_id in str(name).lower().replace(' ', ''):
                fvalue = play_pyaudio_obj.get_format_from_width(play_wf.getsampwidth())
                try:
                    play_stream_obj = play_pyaudio_obj.open(format=fvalue,
                                              channels=play_wf.getnchannels(),
                                              rate=play_wf.getframerate(),
                                              output_device_index=info['index'],
                                              output=True)
                    break
                except Exception:
                    Log.e(self.TAG, 'this channel is used')
                    self.__realse(channel_id)
            time.sleep(0.1)
        Log.i(self.TAG, 'play_obj:%s,play_wf:%s,audio_obj:%s' % (play_stream_obj, play_wf, play_pyaudio_obj))
        return play_stream_obj, play_wf, play_pyaudio_obj

    def __aresaw_maya_play_audio(self, audio_name, channel_id='ch12'):
        """"
                                使用play_wf将文件读取出来，使用play_stream_obj将文件进行播放
        """
        k = self.__aresaw_maya_key(channel_id)
        try:
            play_stream_obj, play_wf, play_pyaudio_obj = \
                self.__aresaw_maya_open_play_audio(audio_name, channel_id)
    
            if not play_stream_obj:
                Log.i(self.TAG, 'no play_stream_obj')
                return None
            self.v_play_flag_dict[k] = 'start'
            while self.v_play_flag_dict[k] != 'stop':
                if self.v_play_flag_dict[k] == 'pause':
                    continue
                data = play_wf.readframes(self.DEFAULT_CHUNK)
                if 0 == len(data):
                    play_wf.rewind()
                    continue
                play_stream_obj.write(data)
        finally:
            play_stream_obj.stop_stream()
            play_stream_obj.close()
            play_pyaudio_obj.terminate()
            play_wf.close()

    def back_paly_and_get_mos(self, play_line, record_line, algorithm, play_file, timeout_seconds=15):
    # 第一个线程启动音频文件录制
        record_file = self.__aw_maya_start_sample(record_line, play_file)
        self.__aw_maya_start_play(play_file, play_line)
        self.node_time = timeout_seconds
        time.sleep(self.node_time)
        self.__aw_maya_stop_play(play_line)
        self.__aw_maya_stop_sample(record_line)
        time.sleep(1)
        # 首先判断是否生成文件
        if os.path.exists(record_file):
            try: 
                wf = wave.open(record_file, 'rb')
                # 检查录音文件是否单通道
                if wf.getnchannels() == 1:
                    Log.i(self.TAG, 'The file format supports algorithm scoring')
                else:
                    # 抛异常 需要处理一下
                    Log.e(self.TAG, 'The file not format supports algorithm scoring')
                    raise InvalidParaException('channel', 'channel must be Single channel')
            finally:
                wf.close()
        else:
            Log.i(self.TAG, 'No recording file generated')
            return None
        ret = self.__start_evaluate_audio(record_file, algorithm, play_file)
        if ret:
            Log.i(self.TAG, 'already get correct mos value')
            return ret, record_file
        return self.BACK_DEFAULT_VALUE

    def start_back_mos_value(self, play_line, record_line, algorithm, play_file, timeout_seconds, deal_mos):
        mos_li = []
        record_li = []
        orgin_file_li = []
        start_time_li = []
        end_time_li = []
        self.v_mos_flag_dict = True
        while self.v_mos_flag_dict == True:
            start_time_li.append(datetime.datetime.now().strftime('%H:%M:%S'))
            mos, record_file = self.back_paly_and_get_mos(play_line, record_line, algorithm, play_file, timeout_seconds)
            mos_li.append(float(mos))
            record_li.append(record_file)
            orgin_file_li.append(play_file)
            end_time_li.append(datetime.datetime.now().strftime('%H:%M:%S'))
        
        if deal_mos and (len(mos_li) > 2):
            mos_li.remove(max(mos_li))
            mos_li.remove(min(mos_li))  

        self.save_mos_value_xls(record_li, orgin_file_li, start_time_li, end_time_li, mos_li, record_line, play_line)
        self.mos_li = mos_li
        self.avg_mos = sum(mos_li) / len(mos_li)
        self.biggest_mos = max(mos_li)
        self.smallest_mos = min(mos_li)
        self.save_mos_value_head_xls(self.avg_mos)
        
    def stop_back_mos_value(self, th_name):
        self.v_mos_flag_dict = False
        time.sleep(self.node_time * (1 + 0.3))
        if th_name.isAlive():
            print('Thread id : %d' % th_name.ident)
            code = ErrorCode(DftCode.COMMON_MODULE, 'error_config_error')
            raise DftException(code, 'Thread stop exception.')
        else:
            return self.mos_li

    def save_mos_value_xls(self, record_file_li, orgin_file_li, start_time_li, end_time_li, mos_li, record_line, play_line):
        book_obj = xlwt.Workbook(encoding="utf-8", style_compression=0)
        sheet_obj = book_obj.add_sheet('语音质量评分表', cell_overwrite_ok=True)
        title_li = ['id', '录音文件', '原始文件', '录音开始时间', '录音结束时间', 'mos分', '输入通道:%s' % record_line, '输出通道:%s' % play_line]
        id_li = list(range(1, len(mos_li) + 1))
        value_li = [id_li, record_file_li, orgin_file_li, start_time_li, end_time_li, mos_li]
        for row in range(len(value_li) + 2):
            sheet_obj.write(0, row, title_li[row])
        for row in range(len(mos_li)):
            for col in range(len(value_li)):
                sheet_obj.write(row + 1, col, value_li[col][row])
        # 空三行
        length = len(mos_li) + 3
        mos_name_li = ['最大值mos', '最小值mos', '平均值mos']
        mos_value_li = [max(mos_li), min(mos_li), sum(mos_li) / len(mos_li)]
        for i in range(3):
            sheet_obj.write(length + i, 0, mos_name_li[i])
            sheet_obj.write(length + i, 1, mos_value_li[i])
        time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        report_recent_dir = self.get_report_path()
        polqa_dir = report_recent_dir + r'\mos' + '\\' + self.case_name
        book_obj.save(polqa_dir + '\\' + time_str + r'_mos_value.xls')
        
    def save_mos_value_head_xls(self, avg_mos):
        """
            总工程平均mos.xls文件生成
        """
        book_obj = xlwt.Workbook(encoding="utf-8", style_compression=0)
        sheet_obj = book_obj.add_sheet('语音质总分表', cell_overwrite_ok=True)
        title_li = ['用例名称', '平均mos分']
        value_li = [self.case_name, avg_mos]
        report_recent_dir = self.get_report_path()
        head_xls_path = report_recent_dir + r'\mos\ALL_MOS_VALUE.xls'
        if not os.path.exists(head_xls_path):
            for col in range(len(title_li)):
                sheet_obj.write(0, col, title_li[col])  
            rows = 1 
            for col in range(len(value_li)):
                sheet_obj.write(rows, col, value_li[col]) 
            book_obj.save(head_xls_path)
        else:
            rexcel = open_workbook(head_xls_path, formatting_info=True)
            rows = rexcel.sheets()[0].nrows
            excel = copy(rexcel) 
            sheet_obj = excel.get_sheet(0)
            for col in range(len(value_li)):
                sheet_obj.write(rows, col, value_li[col])
            excel.save(head_xls_path)
                    
    def __start_and_get_evaluate_result_pesq_exe(self, record_file, play_file):
        report_recent_dir = self.get_report_path()
        pesq_path = get_resource_path('mos') + r'\pesq.exe'    
        mos_dir = report_recent_dir + r'\mos' + '\\' + self.case_name             
        deal_mos_dir = '\\\\?\\' + report_recent_dir + r'\mos' + '\\' + self.case_name
        time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        pesq_dir = mos_dir + '\\' + time_str + 'pesq.txt'
        if not os.path.exists(deal_mos_dir):
            os.makedirs(deal_mos_dir)
        cmd = r'%s +8000 %s %s > %s' % (pesq_path, play_file, record_file, pesq_dir)
        Log.i(self.TAG, cmd)
        os.system(cmd)
        with open(pesq_dir, 'r', encoding='utf-8') as f:
            for single_line in f:
                single_line = single_line.strip().split('\t')[0]
                if 'Raw MOS, MOS-LQO' in single_line or '(MOS-LQO)' in single_line:
                    mos_value = single_line.split('= ')[-1]
                    Log.i(self.TAG, 'pesq mos value is ---> %s' % mos_value)
                    break
            else:
                err_msg = single_line
                Log.e(self.TAG, 'pesq error is ---> %s' % err_msg)
                return None
        return mos_value

    def __start_and_get_evaluate_result_polqa(self, record_file, play_file):
        report_recent_dir = self.get_report_path()
        time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        polqa_path = get_resource_path('mos') + r'\PolqaOemDemo64.exe'
        mos_dir = report_recent_dir + r'\mos' + '\\' + self.case_name
        deal_mos_dir = '\\\\?\\' + report_recent_dir + r'\mos' + '\\' + self.case_name
        polqa_dir = mos_dir + '\\' + time_str + 'polqa.txt'
        if not os.path.exists(deal_mos_dir):
            os.makedirs(deal_mos_dir)
        mode_li = ['NB', 'SWB']  # 8000 和 48000,默认48000  volte使用宽带48000  -Version 2参数很重要
        cmd = r'%s -Ref %s -Test %s -Version 2 -LC %s > %s' % (polqa_path, play_file, record_file, mode_li[1], polqa_dir)
        Log.i(self.TAG, cmd)
        os.system(cmd)
        with open(polqa_dir, 'r', encoding='utf-8') as f:
            for single_line in f:
                single_line = single_line.strip().split('\t')[0]
                if 'MOS-LQO' in single_line:
                    mos_value = single_line.split(': ')[-1]
                    Log.i(self.TAG, 'polqa mos value is ---> %s' % mos_value)
                    break
            else:
                err_msg = single_line
                Log.e(self.TAG, 'polqa error is ---> %s' % err_msg)
                return None
        return mos_value
    
    def __realse(self, channel_id='ch12'):
        """
        maya_id:maya信息
        :return:True 初始化成功，False 初始化失败
        """
        p = pyaudio.PyAudio()
        device_length = p.get_device_count()
        if device_length == 0:
            p.terminate()
            Log.i(self.TAG, 'no any sound_card information,realse is failed')
            return None
        for i in range(device_length):
            audio_name = p.get_device_info_by_index(i)['name']
            if str(channel_id).lower() in audio_name.lower():
                p.terminate()
                Log.i(self.TAG, 'maya sound_card realse is succeed')
                return True
            return None

    def __start_evaluate_audio(self, record_file, algorithm, ref_file):
        mos_ret = None
        if algorithm == 'PESQ':
            mos_ret = self.__start_and_get_evaluate_result_pesq_exe(record_file, ref_file)
        elif algorithm == 'POLQA':
            mos_ret = self.__start_and_get_evaluate_result_polqa(record_file, ref_file)
        else:
            Log.i(self.TAG, 'new algorithm,need continue to develop')
        return mos_ret

    def multi_cast_one_play_others_mos(self, channel_id, record_id_list_string, algorithm, play_file, timeout_seconds):
        mos_li = []
        for record_line in record_id_list_string:
            ret = self.back_paly_and_get_mos(channel_id, record_line, algorithm, play_file, timeout_seconds)
            mos_li.append(ret)
        return mos_li
    
    
