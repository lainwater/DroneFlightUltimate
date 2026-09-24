from datetime import datetime
from time import sleep
import socket
import threading
from pynput import keyboard
import cv2


### UTIL START ###
class Util:
    def __init__(self, title):
        self.title = title

    def log(self, msg, option):
        print(f"[{option}][{self.title}]: {datetime.now()} - {msg}")

    def string_to_number(self, s):
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return s

    def make_status_data_dic(self, state_msg):
        state_str = state_msg.decode(encoding="utf-8")
        state_dict = {}
        for item in state_str.strip().split(";"):
            if item:
                key, value = item.split(":", 1)
                state_dict[key] = self.string_to_number(value)
        return state_dict


### UTIL END ###

###-DRONE START ###
mission_pad_detected = False


class Tello:
    def __init__(self, name="TELLO 1", info_port=8000, video_port=3000, cmd_drone_port=8889, cmd_pc_port=9000, ip="192.168.10.1", id=1):
        self.cmd_sock = None
        self.recv_sock = None
        self.tello_address = None
        self.ip = ip
        self.cmd_port = cmd_drone_port
        self.cmd_pc_port = cmd_pc_port
        self.info_port = info_port
        self.video_port = video_port
        self.utility = Util(name)
        self.state_data = None
        self.id = id
        self.name = name

    def connect(self):
        try:
            self.utility.log("Connecting . . .", "STATE")
            self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.cmd_sock.bind(("", self.cmd_pc_port))
            self.tello_address = (self.ip, self.cmd_port)
            self.utility.log("Connected!", "STATE")

            self.utility.log("Starting listener . . .", "STATE")
            self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_sock.bind(("", self.info_port))
            self.utility.log("Started listener!", "STATE")

            self.utility.log("Putting Drone in SDK mode . . .", "STATE")
            response = self.send_and_receive("command")
            self.utility.log(f"Drone now in SDK mode. Respone: {response}!", "STATE")

            self.utility.log("Setting Drone Video and Info Port . . .", "STATE")
            response = self.send_and_receive(f"port {self.info_port} {self.video_port}")
            self.utility.log(f"Drone Video and Info Port now set. Respone: {response}!", "STATE")

            self.utility.log("Starting Battery Check . . .", "STATE")
            battery = self.utility.string_to_number(self.send_and_receive("battery?"))
            if int(battery) < 30:
                self.utility.log(f"Battery Low: {battery} %", "WARNING")
            elif int(battery) > 85:
                self.utility.log(f"Battery is High: {battery} %", "WARNING")
            elif battery == None:
                self.utility.log(f"Battery Check failed: {battery}", "WARNING")
            else:
                self.utility.log(f"Battery is Mid: {battery} %", "WARNING")

        except Exception as e:
            self.utility.log(f"Error occurred while connecting to Tello: {e}", "ERROR")

    def wifi_connect(self, ssid, pw):
        self.utility.log(f"Conneciting to Wifi {ssid}", "WIFI")
        x = self.send_and_receive(f"ap {ssid} {pw}")
        sleep(0.5)
        self.utility.log(f"Now Connected to Wifi {ssid}. Recieved {x}", "WIFI")

    def close(self):
        self.utility.log("Closing connection to drone. Landing first, if fail send Emergency . . .", "STATE")
        try:
            try:
                self.send_and_receive("land")
            except:
                self.send("emergency")
                self.send("emergency")
                self.send("emergency")
            self.cmd_sock.close()
            self.recv_sock.close()
            self.utility.log("Closed connection to drone!", "STATE")
        except Exception as e:
            self.utility.log(f"Error occurred while closing sockets: {e}", "ERROR")

    def send_and_receive(self, msg, timeout=20):
        self.cmd_sock.settimeout(timeout)  # 0 = non blocking,  None = blocking, or time as non negative float
        self.utility.log(f"Sending Command: {msg}.", "CMD")
        try:
            self.cmd_sock.sendto(msg.encode(encoding="utf-8"), self.tello_address)
            data, server = self.cmd_sock.recvfrom(1024)
            self.utility.log(data.decode(encoding="utf-8"), "RESPONSE")
            return data.decode(encoding="utf-8")
        except Exception as e:
            self.utility.log(f"Error occurred while sending&recieving command: {msg}. Error: {e}", "ERROR")

    def send(self, msg):
        try:
            self.utility.log(f"Sending Command: {msg}.", "CMD")
            self.cmd_sock.sendto(msg.encode(encoding="utf-8"), self.tello_address)
        except Exception as e:
            self.utility.log(f"Error occurred while sending command: {msg}. Error: {e}", "ERROR")

    def on_receive_state(self, callback):
        self.utility.log("Starting to listen for state information . . .", "STATE")
        mission_pad_detected = False
        while True:
            try:
                data, server = self.recv_sock.recvfrom(1024)
                data = self.utility.make_status_data_dic(data)
                callback(data)
                self.state_data = data
                if not mission_pad_detected and data["mid"] > 0:
                    self.send("rc 0 0 0 0")
                    mission_pad_detected = True
                    self.utility.log("PAD DETECTED", "STATUS")
            except Exception as e:
                self.utility.log(f"Error occured while listening to Status Info. Error: {e}", "ERROR")
                break

    ### MISSIONS ###
    def init_dummy(self):
        self.send_and_receive("up 20")
        self.send_and_receive("down 20")

    def go_pad(self):
        self.send_and_receive(f"go 0 0 80 20 m-1")

    def search_grid_single(self):
        self.utility.log("Search Mission Start!", "STATUS")
        grid_lenght = [94 - 10, 25, 104 - 10, 25, 104 - 10, 25, 104 - 10, 25, 104 - 10, 21, 100 - 10, 25, 74 - 10, 22, 63 - 10, 168 - 10]
        grid_turns = ["cw", "cw", "ccw", "ccw", "cw", "cw", "ccw", "ccw", "cw", "cw", "ccw", "ccw", "cw", "cw", "cw", "cw"]
        fail = False
        self.send_and_receive("takeoff")
        sleep(3)
        self.init_dummy()
        sleep(1)
        self.send_and_receive("speed 20")
        sleep(1)
        self.send_and_receive("up 30")
        sleep(1)
        for i in range(len(grid_lenght)):
            if not mission_pad_detected:
                if i & 1 == 0:
                    x = self.send_and_receive(f"forward {grid_lenght[i]}")
                else:
                    x = self.send_and_receive(f"{grid_turns[i]} 90")
                sleep(1)
                if x != "ok":
                    self.utility.log("Did not get 'ok' back. Aborting Mission", "WARNING")
                    fail = True
                    break
            elif int(self.state_data["bat"]) < 30:
                self.utility.log("Battery low! Please land the drone! Else: Continuing", "WARNING")
                fail = True
            else:
                self.send_and_receive("back 20")
                sleep(2)
                if data["mid"] > 0:
                    self.send_and_receive("go 0 0 80 20 m-2")
                sleep(3)
                self.send_and_receive("land")
                break

        if not fail:
            self.utility.log("Search Mission Done!", "STATUS")
        else:
            self.utility.log("Search Mission Failed", "STATUS")

    def square_motion(self, side_length, side):
        if side == "right":
            cw_or_ccw = "cw"
        elif side == "left":
            cw_or_ccw = "ccw"
        self.utility.log("Square Mission Start!", "STATUS")
        fail = False
        for i in range(4):
            sleep(3)
            response1 = self.send_and_receive(f"forward {side_length}")
            sleep(3)
            response2 = self.send_and_receive(f"{cw_or_ccw} 90")
            if response1 != "ok" or response2 != "ok":
                self.send_and_receive("rc 0 0 0 0")
                fail = True
                break
        if not fail:
            self.utility.log(f"Square Mission Done!", "STATUS")
        else:
            self.utility.log(f"Square Mission Failed!", "STATUS")


### DRONE END ###

### CONTROLLER START ###
drone_select = [True, True]


class Controller:
    def __init__(self, drone, control_speed=50):
        self.drone = drone
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.control_speed = control_speed
        self.utility = Util("KEYBOARD")
        self.cam = 0

    def start_keyboard_listener(self):
        try:
            self.utility.log("Starting keyboard listener . . .", "STATE")
            self.listener.start()
        except Exception as e:
            self.utility.log(f"Error occurred while starting keyboard listener: {e}", "ERROR")

    def on_press(self, key):
        if drone_select[self.drone.id - 1] == True:
            if hasattr(key, "char"):
                if key.char == "t":
                    self.drone.send("takeoff")
                if key.char == "l":
                    self.drone.send("land")
                if key.char == "w":
                    self.drone.send(f"rc 0 0 {self.control_speed} 0")
                if key.char == "s":
                    self.drone.send(f"rc 0 0 -{self.control_speed} 0")
                if key.char == "a":
                    self.drone.send(f"rc 0 0 0 -{self.control_speed}")
                if key.char == "d":
                    self.drone.send(f"rc 0 0 0 {self.control_speed}")
                if key.char == "c":
                    if self.cam == 0:
                        self.drone.send(f"downvision 1")
                        self.cam = 1
                    elif self.cam == 1:
                        self.drone.send(f"downvision 0")
                        self.cam = 0
                if key.char == "i":
                    dummy = threading.Thread(target=self.drone.init_dummy)
                    dummy.start()
                if key.char == "g":
                    gopad = threading.Thread(target=self.drone.go_pad)
                    gopad.start()
                if key.char == "o":
                    search_mission = threading.Thread(target=self.drone.search_grid_single)
                    search_mission.start()
                if key.char == "0":
                    drone_select[0] = True
                    drone_select[1] = True
                if key.char == "1":
                    drone_select[0] = True
                    drone_select[1] = False
                if key.char == "2":
                    drone_select[0] = False
                    drone_select[1] = True
            else:
                if key == keyboard.Key.up:
                    self.drone.send(f"rc 0 {self.control_speed} 0 0")
                if key == keyboard.Key.down:
                    self.drone.send(f"rc 0 -{self.control_speed} 0 0")
                if key == keyboard.Key.left:
                    self.drone.send(f"rc -{self.control_speed} 0 0 0")
                if key == keyboard.Key.right:
                    self.drone.send(f"rc {self.control_speed} 0 0 0")
                if key == keyboard.Key.space:
                    self.drone.send("emergency")

    def on_release(self, key):
        if drone_select[self.drone.id - 1] == True:
            if hasattr(key, "char"):
                if key.char == "o" or key.char == "u":
                    pass
                elif key.char in ("w", "s", "a", "d"):
                    self.drone.send("rc 0 0 0 0")
            else:
                if key == keyboard.Key.esc:
                    self.drone.close()
                    return False
                elif key in (keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right):
                    self.drone.send("rc 0 0 0 0")


### CONTROLLER END ###


### VIDEOSTREAM START ###
class VideoStream:
    def __init__(self, drone, keyboard):
        self.drone = drone
        self.udp = f"udp://0.0.0.0:{self.drone.video_port}"
        self.drone_data = None
        self.cap = None
        self.utility = Util(self.drone.name)
        self.keyboard = keyboard

    def connect_stream(self):
        try:
            self.utility.log("Starting video stream . . .", "STATE")
            sleep(0.5)
            self.drone.send_and_receive("streamon")
            sleep(1)
            self.cap = cv2.VideoCapture(self.udp)
            sleep(0.5)
            self.utility.log("Started video stream!", "STATE")
        except Exception as e:
            self.utility.log(f"Error occured while starting the Stream. Error: {e}", "ERROR")

    def close(self):
        try:
            self.utility.log("Closing video stream . . .", "STATE")
            self.drone.send_and_receive(f"streamoff")
            self.cap.release()
            cv2.destroyWindow(self.drone.name)
            self.utility.log("Closed video stream!", "STATE")
        except Exception as e:
            self.utility.log(f"Error occured while closing the Stream. Error: {e}", "ERROR")

    def display_update(self):
        sleep(10)
        cv2.namedWindow(self.drone.name)
        sleep(1)
        while True:
            received, self.frame = self.cap.read()
            if not received:
                self.utility.log("No Video Recieved. Trying again in 5 seconds...", "ERROR")
                sleep(5)
                received, self.frame = self.cap.read()
                if not received:
                    self.utility.log("No Video Recieved. Exiting", "ERROR")
                    break

            self.display_text(text=self.drone.name, position=(30, 50))
            if self.drone_data != None:
                self.display_text(text=f"mid: {self.drone_data.get('mid')}", position=(30, 150))
                self.display_text(text=f"bat: {self.drone_data.get('bat')}%", position=(30, 200))
                self.display_text(text=f"temp: {self.drone_data.get('temph')} C", position=(30, 250))
                self.display_text(text=f"height: {self.drone_data.get('h')} cm", position=(30, 300))

            if self.keyboard.cam == 1:
                frame_display = self.rescale_frame(frame=self.frame, scale=2)
            elif self.keyboard.cam == 0:
                frame_display = self.frame
            cv2.imshow(self.drone.name, frame_display)

            if cv2.waitKey(1) & 0xFF == 27:
                self.utility.log("ESC key pressed. Exiting video stream display loop.", "STATE")
                self.close()
                break

    def display_text(self, text=None, position=(30, 50), font=cv2.FONT_HERSHEY_SIMPLEX, font_scale=1, color=(255, 0, 115), thickness=2):
        cv2.putText(self.frame, text, position, font, font_scale, color, thickness)

    def data_update(self, data):
        self.drone_data = data

    def rescale_frame(self, frame, scale):  # works for image, video, live video
        width = int(frame.shape[1] * scale)
        height = int(frame.shape[0] * scale)
        dimensions = (width, height)
        return cv2.resize(frame, dimensions, interpolation=cv2.INTER_AREA)


### VIDEOSTREAM END ###


### Scripts START ###
def main_swarm():
    yellow = Tello(name="Yellow[1]", ip="10.39.33.2", cmd_pc_port=9000, info_port=8000, video_port=3000, id=1)
    yellow_controller = Controller(drone=yellow)
    yellow_stream = VideoStream(drone=yellow, keyboard=yellow_controller)
    yellow_status = threading.Thread(target=yellow.on_receive_state, args=(lambda x: yellow_stream.data_update(x),), daemon=True)
    yellow_stream_thread = threading.Thread(target=yellow_stream.display_update, daemon=True)

    white = Tello(name="White[2]", ip="10.39.33.162", cmd_pc_port=9001, info_port=8001, video_port=3001, id=2)
    white_controller = Controller(drone=white)
    white_stream = VideoStream(drone=white, keyboard=white_controller)
    white_status = threading.Thread(target=white.on_receive_state, args=(lambda x: white_stream.data_update(x),), daemon=True)
    white_stream_thread = threading.Thread(target=white_stream.display_update, daemon=True)

    yellow.connect()
    white.connect()
    sleep(5)
    yellow_stream.connect_stream()
    white_stream.connect_stream()

    yellow_controller.start_keyboard_listener()
    yellow_status.start()
    yellow_stream_thread.start()

    white_controller.start_keyboard_listener()
    white_status.start()
    white_stream_thread.start()

    white_stream_thread.join()
    yellow_stream_thread.join()
    sleep(30)


def main_single():
    yellow = Tello(name="Yellow[1]")
    yellow_controller = Controller(drone=yellow)
    yellow_stream = VideoStream(drone=yellow, keyboard=yellow_controller)
    yellow_status = threading.Thread(target=yellow.on_receive_state, args=(lambda x: yellow_stream.data_update(x),), daemon=True)
    yellow_stream_thread = threading.Thread(target=yellow_stream.display_update, daemon=True)
    yellow.connect()
    sleep(5)
    yellow_stream.connect_stream()

    yellow_controller.start_keyboard_listener()
    yellow_status.start()
    yellow_stream_thread.start()
    yellow_stream_thread.join()
    sleep(30)


def wifi_connect():
    drone = Tello()
    drone.connect()
    drone.wifi_connect("Thinhphone", "thinhnguyen")


### SCRIPTS END ###


### MAIN ### TELLO 1: FE2874    TELLO 2:
def main():
    try:
        main_logger = Util("MAIN")
        main_single()
    except KeyboardInterrupt:
        main_logger.log("Programm Interupted by User...", "STATUS")
    except Exception as e:
        main_logger.log("Programm Interupted by User...", "ERROR")
    finally:
        pass


if __name__ == "__main__":
    main()
