#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

#import MicrophoneStream as MS
import RPi.GPIO as GPIO
import user_auth as UA
import audioop
import ktkws # KWS
import grpc
import gigagenieRPC_pb2
import gigagenieRPC_pb2_grpc
import argparse, pafy, ffmpeg, pyaudio, os, time
import wave, urllib, bs4

from urllib.request import urlopen, Request
from six.moves import queue
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ctypes import *
from datetime import datetime

KWSID = ['기가지니', '지니야', '친구야', '자기야']

HOST = 'gate.gigagenie.ai'
FORMAT = pyaudio.paInt16
CHANNELS = 1
PORT = 4080
RATE = 16000
CHUNK = 512

#GPIO.cleanup()

DEVELOPER_KEY = "AIzaSyC59PZS5PUvVliiJoWQxo2p4O7Bl5U3_Pc"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(31, GPIO.OUT)
btn_status = False

play_flag = 0


drug_h = 9
drug_m = 30
drug_flag = 0

rice_h = 9
rice_m = 0
rice_flag = 0

def callback(channel):
    print("falling edge detected from pin {}".format(channel))
    global btn_status
    btn_status = True
    print(btn_status)
    global play_flag
    play_flag = 1
    
GPIO.add_event_detect(29, GPIO.FALLING, callback=callback, bouncetime=10)

ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
  dummy_var = 0
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
asound = cdll.LoadLibrary('libasound.so')
asound.snd_lib_error_set_handler(c_error_handler)

#example 1

def detect():
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        
        for content in audio_generator:
            now = datetime.now()
            
            if(now.hour == int(drug_h) and now.minute == int(drug_m) and now.second == 0) :
                drug_flag = 1
                output_file = "drug_text.wav"
                getText2VoiceStream("약 먹을 시간입니다.", output_file)
                play_file(output_file)
            
            elif(now.hour == int(rice_h) and now.minute == int(rice_m) and now.second == 0):
                rice_flag = 1
                output_file = "rice_text.wav"
                getText2VoiceStream("식사 하실 시간입니다.", output_file)
                play_file(output_file)
            
            rc = ktkws.detect(content)
            rms = audioop.rms(content,2)
            #print('audio rms = %d' % (rms))
            if (rc == 1):
                play_file("../data/sample_sound.wav")
                return 200

def test(key_word = '기가지니'):
	rc = ktkws.init("../data/kwsmodel.pack")
	print ('init rc = %d' % (rc))
	rc = ktkws.start()
	print ('start rc = %d' % (rc))
	print ('\n호출어를 불러보세요~\n')
	ktkws.set_keyword(KWSID.index(key_word))
	rc = detect()
	print ('detect rc = %d' % (rc))
	print ('\n\n호출어가 정상적으로 인식되었습니다.\n\n')
	ktkws.stop()
	return rc

#example 2
    
def generate_request():
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
    
        for content in audio_generator:
            message = gigagenieRPC_pb2.reqVoice()
            message.audioContent = content
            yield message
            
            rms = audioop.rms(content,2)
            #print_rms(rms)

def getVoice2Text():	
    print ("\n\n음성인식을 시작합니다.\n\n종료하시려면 Ctrl+\ 키를 누루세요.\n\n\n")
    channel = grpc.secure_channel('{}:{}'.format(HOST, PORT), UA.getCredentials())
    stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)
    request = generate_request()
    resultText = ''
    for response in stub.getVoice2Text(request):
        if response.resultCd == 200: # partial
            print('resultCd=%d | recognizedText= %s' 
                  % (response.resultCd, response.recognizedText))
            resultText = response.recognizedText
        elif response.resultCd == 201: # final
            print('resultCd=%d | recognizedText= %s' 
                  % (response.resultCd, response.recognizedText))
            resultText = response.recognizedText
            break
        else:
            print('resultCd=%d | recognizedText= %s' 
                  % (response.resultCd, response.recognizedText))
            break

    print ("\n\n인식결과: %s \n\n\n" % (resultText))
    return resultText

#example 4

def getText2VoiceStream(inText,inFileName):

	channel = grpc.secure_channel('{}:{}'.format(HOST, PORT), UA.getCredentials())
	stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)

	message = gigagenieRPC_pb2.reqText()
	message.lang=0
	message.mode=0
	message.text=inText
	writeFile=open(inFileName,'wb')
	for response in stub.getText2VoiceStream(message):
		if response.HasField("resOptions"):
			print ("\n\nResVoiceResult: %d" %(response.resOptions.resultCd))
		if response.HasField("audioContent"):
			print ("Audio Stream\n\n")
			writeFile.write(response.audioContent)
	writeFile.close()
	return response.resOptions.resultCd

#example 5

def queryByText(text):

	channel = grpc.secure_channel('{}:{}'.format(HOST, PORT), UA.getCredentials())
	stub = gigagenieRPC_pb2_grpc.GigagenieStub(channel)

	message = gigagenieRPC_pb2.reqQueryText()
	message.queryText = text
	message.userSession = "1234"
	message.deviceId = "yourdevice"
		
	response = stub.queryByText(message)

	print ("\n\nresultCd: %d" % (response.resultCd))
	if response.resultCd == 200:
		print ("\n\n\n질의한 내용: %s" % (response.uword))
		#dssAction = response.action
		for a in response.action:
			response = a.mesg
		parsing_resp = response.replace('<![CDATA[', '')
		parsing_resp = parsing_resp.replace(']]>', '')
		return parsing_resp
		#return response.url
	else:
		print ("Fail: %d" % (response.resultCd))
		#return None	 


#microphoneStream

# MicrophoneStream - original code in https://goo.gl/7Xy3TT
class MicrophoneStream(object):
	"""Opens a recording stream as a generator yielding the audio chunks."""
	def __init__(self, rate, chunk):
		self._rate = rate
		self._chunk = chunk

		# Create a thread-safe buffer of audio data
		self._buff = queue.Queue()
		self.closed = True

	def __enter__(self):
		self._audio_interface = pyaudio.PyAudio()
		self._audio_stream = self._audio_interface.open(
			format=pyaudio.paInt16,
			channels=1, rate=self._rate,
			input=True, frames_per_buffer=self._chunk,
			# Run the audio stream asynchronously to fill the buffer object.
			# This is necessary so that the input device's buffer doesn't
			# overflow while the calling thread makes network requests, etc.
			stream_callback=self._fill_buffer,
		)

		self.closed = False

		return self

	def __exit__(self, type, value, traceback):
		self._audio_stream.stop_stream()
		self._audio_stream.close()
		self.closed = True
		# Signal the generator to terminate so that the client's
		# streaming_recognize method will not block the process termination.
		self._buff.put(None)
		self._audio_interface.terminate()

	def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
		"""Continuously collect data from the audio stream, into the buffer."""
		self._buff.put(in_data)
		return None, pyaudio.paContinue

	def generator(self):
		while not self.closed:
			# Use a blocking get() to ensure there's at least one chunk of
			# data, and stop iteration if the chunk is None, indicating the
			# end of the audio stream.
			chunk = self._buff.get()
			if chunk is None:
				return
			data = [chunk]

			# Now consume whatever other data's still buffered.
			while True:
				try:
					chunk = self._buff.get(block=False)
					if chunk is None:
						return
					data.append(chunk)
				except queue.Empty:
					break

			yield b''.join(data)
# [END audio_stream]

def play_file(fname):
	# create an audio object
	wf = wave.open(fname, 'rb')
	p = pyaudio.PyAudio()
	chunk = 1024

	# open stream based on the wave object which has been input.
	stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
					channels=wf.getnchannels(),
					rate=wf.getframerate(),
					output=True)

	# read data (based on the chunk size)
	data = wf.readframes(chunk)

	# play stream (looping from beginning of file to the end)
	while len(data) > 0:
		# writing to the stream is what *actually* plays the sound.
		stream.write(data)
		data = wf.readframes(chunk)

		# cleanup stuff.
	stream.close()

#youtube music streaming

def youtube_search(options):
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                        developerKey=DEVELOPER_KEY)
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--q', help='Search term', default=options)
        parser.add_argument('--max-results', help='Max results', default=25)
        args = parser.parse_args();
        search_response = youtube.search().list(
            q=args.q,
            part="id,snippet",
            maxResults=args.max_results
            ).execute()
        
        videos = []
        url = []
        
        for search_result in search_response.get("items", []):
            if search_result['id']['kind'] == 'youtube#video':
                videos.append('%s (%s)' % (search_result['snippet']['title'],search_result['id']['videoId']))
                url.append(search_result['id']['videoId'])
            
        resultURL = "https://www.youtube.com/watch?v=" + url[0]
        return resultURL
        
    except:
        print("youtube Error")


def play_with_url(play_url):
    print(play_url)
    video = pafy.new(play_url)
    best = video.getbestaudio()
    playurl = best.url
    global play_flag
    play_flag = 0
    
    pya = pyaudio.PyAudio()
    stream = pya.open(format=pya.get_format_from_width(width=2), channels=1, rate=16000,
                      output=True)
    
    try:
        process = (ffmpeg
                   .input(playurl, err_detect='ignore_err', reconnect=1, reconnect_streamed=1,
                          reconnect_delay_max=5)
                   .output('pipe:', format='wav', audio_bitrate=16000, ab=64, ac=1, ar='16k')
                   .overwrite_output()
                   .run_async(pipe_stdout=True)
                   )
        
        while True:
            if play_flag == 0 :
                in_bytes = process.stdout.read(4096)
                if not in_bytes:
                    break
                stream.write(in_bytes)
            else:
                break
    finally:
        stream.stop_stream()
        stream.close()


#Get Weather

def getWeather(location = '거의동'):
    
    enc_location = urllib.parse.quote(location + '+날씨')
    url = 'https://search.naver.com/search.naver?ie=utf8&query=' + enc_location
    req = Request(url)
    page = urlopen(req)
    html = page.read()
    soup = bs4.BeautifulSoup(html, 'html5lib')
    
    info_weather = location + '의 날씨는 현재'+ soup.find('p', class_='info_temperature').find('span', class_='todaytemp').text + '도 '
    tmp = soup.find('ul', class_='info_list').find('p', class_='cast_txt').text
    tmp = "".join(tmp.split(','))
    info_weather = info_weather + tmp
    
    return info_weather

def main():
    global drug_h
    global drug_m
    
    global rice_h
    global rice_m
    
    while 1:
        recog=test(KWSID[0])
        if recog == 200:
            GPIO.output(31, GPIO.HIGH)
            print('KWS Dectected ...\n Start STT...')
            text = getVoice2Text()
            print('Recognized Text: '+ text)
            if text.find("노래 틀어줘") >= 0 or text.find("노래 들려줘") >=0 :
                split_text = text.split(" ")
                serach_text = split_text[split_text.index("노래") -1]
                output_file = "search_text.wav"
                getText2VoiceStream("유튜브에서 " + serach_text + "노래를 재생합니다.", output_file)
                play_file(output_file)
                
                result_url = youtube_search(serach_text)
                play_with_url(result_url)
                      
            elif text.find("알람") >= 0 :
                if text.find("시") >= 0 :
                    if text.find("약") >= 0 :
                        if text.find("분") >= 0:
                            
                            split_text = text.split(" ")
                            tmp_h = split_text[split_text.index("약") -2]
                            hour = tmp_h.split("시")
                            tmp_m = split_text[split_text.index("약") -1]
                            min = tmp_m.split("분")
                            
                            
                            drug_h = hour[0]
                            drug_m = min[0]
                            
                            output_file = "alarm_text.wav"
                            getText2VoiceStream(str(drug_h) + "시" + str(drug_m) + "분에 약 알람이 울립니다." , output_file)
                            play_file(output_file)
                                                  
                        else :
                            split_text = text.split(" ")
                            tmp = split_text[split_text.index("약") -1]
                            hour = tmp.split("시")
                            
                            drug_h = hour[0]
                            drug_m = 0
                            
                            output_file = "alarm_text.wav"
                            getText2VoiceStream(str(drug_h) + "시에 약 알람이 울립니다." , output_file)
                            play_file(output_file)
                            
                            
                    elif text.find("밥") >= 0 :
                        if text.find("분") >= 0:
                            
                            split_text = text.split(" ")
                            tmp_h = split_text[split_text.index("밥") -2]
                            hour = tmp_h.split("시")
                            tmp_m = split_text[split_text.index("밥") -1]
                            min = tmp_m.split("분")
                            
                            
                            rice_h = hour[0]
                            rice_m = min[0]
                            
                            output_file = "alarm_text.wav"
                            getText2VoiceStream(str(rice_h) + "시" + str(rice_m) + "분에 식사 알람이 울립니다." , output_file)
                            play_file(output_file)
                                                  
                        else :
                            split_text = text.split(" ")
                            tmp = split_text[split_text.index("약") -1]
                            hour = tmp.split("시")
                            
                            rice_h = hour[0]
                            rice_m = 0
                            
                            output_file = "alarm_text.wav"
                            getText2VoiceStream(str(rice_h) + "시에 식사 알람이 울립니다." , output_file)
                            play_file(output_file)
                            
                            
                    else :
                        output_file = "alarm_text.wav"
                        getText2VoiceStream("정확한 알람 종류를 말해주세요", output_file)
                        play_file(output_file)
                    
            
            elif text.find("날씨") >= 0 :
                tmp_location = text.split(" ")
                location_index = tmp_location.index("날씨")
                
                location = "".join(tmp_location[:location_index])
                
                result_weather = getWeather(location)
                
                output_file = "weather.wav"
                getText2VoiceStream(result_weather, output_file)
                play_file(output_file)
            
            elif text.find("노래 틀어줘") < 0 or text.find("노래 들려줘") < 0 and text != "" :
                output_file = "talking.wav"
                response_Text = queryByText(text)
                print("%s\n" % (response_Text))
                getText2VoiceStream(response_Text, output_file)
                play_file(output_file)
                
            else :
                output_file = "talking.wav"
                getText2VoiceStream("정확한 명령을 말해주세요", output_file)
                play_file(output_file)
            
            time.sleep(2)
            GPIO.output(31, GPIO.LOW)
            
        else:
            print('KWS Not Dectected ...')

if __name__ == '__main__':
    main()
