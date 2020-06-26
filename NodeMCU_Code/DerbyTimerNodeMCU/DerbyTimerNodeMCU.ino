/* Derby Timer using the Node MCU 
Author: Lee Burchett
lee.r.burchett@gmail.com

Use a node MCU to count pulses in order to get timing for a pinewood derby.
V1 Was the initial, 1 MCU Version
V2 Was a 1 board per track version
V3 Incorporates the local display



Copyright [2019] [Lee R. Burchett]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

*/

//#include <SPI.h>
#include <Wire.h>
#include <ESP8266WiFi.h>
//#include <string.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "MyWIFI_Settings.h"


/*  Set the channel numbers
 *  These are D0,D1,D2,D3,D4,D5,D6,D7,D8,D9/RX,D10/TX,D11/SD3,D12/SD2 
 *  const int channels[]={16,5,4,0,2,14,12,13,15,3,1,10,9};
 *  D0  = 16
 *  D1  = 5
 *  D2  = 4
 *  D3  = 0
 *  D4  = 2
 *  D5  = 14
 *  D6  = 12
 *  D7  = 13
 *  D8  = 15
 *  D9  = 3
 *  D10 = 1
 *  D11 = 10
 *  D12 = 9
http://www.electronicwings.com/nodemcu/nodemcu-gpio-with-arduino-ide */
#define COUNT 14 // Counter Input
#define RESET_IN 12 // Track Reset Input
#define RESET_OUT 4 // Track Reset Output
#define OLED_RESET -1 // Reset pin # (or -1 if sharing Arduino reset pin)
#define OLED_CLK 1 // I2C Clock
#define OLED_SDA 3 // I2C Data 
#define STRLEN 257
#define LOOP_DELAY 25 // in ms. This should be long enough that several pulses arrive
#define LED_PIN 16 // For debug
#define RACING_RATE 12 // Smaller number = faster flash
#define STANDBY_RATE 60 // Smaller number = faster flash
#define POWER_OUT 2 // Turns off the input power when low
#define USER_INPUT 5 // User input through power button


/* OLED Controls
See the example from the Adafruit SD1306 library.*/
#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 32 // OLED display height, in pixels
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
/* End OLED Controls */

unsigned long counts;
unsigned long last_val;
bool is_set=0,
     has_started=0,
     client_connected=0,
     reset_pressed=0,
     OLED_init=0;

const char* ssid = MY_SSID;
const char* password = MY_WIFI_PASSWORD;

const double clock_rate = 1000; /* In Hz */
const int port = MY_PORT;
int i;
int current_rate = STANDBY_RATE;
int press_count = 0;

WiFiServer wifiServer(port);
WiFiClient wifiClient;
WiFiEventHandler mDisconnectHandler;

void race_set();
void on_wifi_disconnected(const WiFiEventStationModeDisconnected& event);
void ICACHE_RAM_ATTR count();
void stop_rx();
void reset_rx();

void setup() {
  byte mac[6];
  byte ip[] = MY_IP;
  byte subnet[] = MY_SUBNET;
  byte gateway[] = MY_GATEWAY;
  mDisconnectHandler = WiFi.onStationModeDisconnected(on_wifi_disconnected);

  /* Start the serial and display interfaces */
  //Serial.begin(115200);
  Wire.begin(OLED_SDA,OLED_CLK);
  
  /* Prepare pin interfaces. */
  pinMode(POWER_OUT, OUTPUT);
  digitalWrite(POWER_OUT, HIGH);
  pinMode(COUNT,INPUT_PULLUP);
  pinMode(RESET_IN,INPUT_PULLUP);
  pinMode(RESET_OUT,OUTPUT);
  digitalWrite(RESET_OUT,HIGH);
  pinMode(USER_INPUT, INPUT_PULLUP);
  pinMode(LED_PIN,OUTPUT);
  attachInterrupt(digitalPinToInterrupt(COUNT), count, CHANGE);

  /* OLED Initialization 
  SSD1306_SWITCHCAPVCC = generate display voltage from 3.3V internally*/
  if(!(OLED_init = display.begin(SSD1306_SWITCHCAPVCC, 0x3C))) { // Address 0x3C for 128x32
    //Serial.println(F("SSD1306 allocation failed"));
    for(i=0;i<5000;i++){
      digitalWrite(LED_PIN,i%2);
      delay(150);
    }
  }
  
  else{
    // Show initial display buffer contents on the screen --
    // the library initializes this with an Adafruit splash screen.
    display.display();
  }

  digitalWrite(LED_PIN,1);
  //Serial.println("Setting up the network");

  /* Get the network up and running */
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid,password);
  while (WiFi.status() != WL_CONNECTED) {   
    delay(200);
  }

  for(i=0;i<5;i++){
   digitalWrite(LED_PIN,i%2);
   delay(350);
  }
  i=0;
  
  wifiServer.begin();
  race_set();   
}

void cut_power(){
  digitalWrite(POWER_OUT,LOW);
}

void ICACHE_RAM_ATTR count(){
  counts++;
}
void static_message(char *msg){
  display.stopscroll();
  display.clearDisplay();
  display.setCursor(0,0);
  display.setTextSize(2);
  display.print(msg);
  display.display();
}
void scrolling_message(char *msg){
  display.clearDisplay();
  display.setCursor(0,0);
  display.setTextSize(2);
  display.println(msg);
  display.display();
  delay(100);
  
  display.startscrollleft(0x00, 0x0F);
}
void send_reset_to_timer(){
  char msg[]="Sending Reset Signal.\n";
  int watchdog=0;
  reset_pressed=true;
  if(wifiClient){
    if(wifiClient.connected()){
      wifiClient.write((uint8_t *)msg,sizeof(msg)); 
    } /* if the client is connected */
  } /* if the client is valid */
  digitalWrite(RESET_OUT,LOW);
  static_message(msg);
  delay(LOOP_DELAY*3); /* Give time for the others to react */
  while(digitalRead(RESET_IN) && watchdog<10){
    delay(LOOP_DELAY*2);
    display.print(".");
    display.display();
    watchdog++;
  }
  digitalWrite(RESET_OUT,HIGH);
  race_set();
}
void reset_rx(){
  reset_pressed=true;
  char msg[]="<Reset recieved.>\n";
  static_message(msg);
  if(wifiClient){
    if(wifiClient.connected()){
      wifiClient.write((uint8_t *)msg,sizeof(msg)); 
    } /* if the client is connected */
  } /* if the client is valid */
  race_set();
}
void check_timer(){
  if(counts == last_val){
    if(has_started && is_set){ /* Things have started, but now we are at the end. */
      is_set=false;
      send_lane_results();
    }
    current_rate = STANDBY_RATE;
  }
  else if(!has_started){
    has_started=true;
    send_start_message();
    current_rate = RACING_RATE;
  }
}
void race_set(){
  //Serial.println("Setting the race up");
  counts = 0;
  last_val = 0;
  is_set = true;
  has_started = false;
  //Serial.println("Sending the ready message.");
  send_ready_message();
  current_rate = STANDBY_RATE;
  //Serial.println("Race setup complete.");
}
void send_start_message(){
  char msg[]= "<GO!>\n";
  char msg2[] = "Racing!";
  if(wifiClient){
    if(wifiClient.connected()){
      wifiClient.write((uint8_t *)msg,sizeof(msg)); 
    } /* if the client is connected */
  } /* if the client is valid */
  scrolling_message(msg2);
} /* send_start_message()*/
void send_lane_results(){
  char msg[64];
  sprintf(msg,"Time:\n%5.3lf",(double)counts/(2.0*clock_rate));
  static_message(msg);
  sprintf(msg,"<Track count:%lu>",counts);
  if(wifiClient){
    if(wifiClient.connected()){
      wifiClient.write((uint8_t *)&msg,strlen(msg)); 
    } /* if the client is connected */
  } /* if the client is valid */
} /* send_lane_results()*/
void send_ready_message(){
  char msg[]= "<Ready to Race.>\n";
    if(wifiClient){
      if(wifiClient.connected()){
        wifiClient.write((uint8_t *)msg,sizeof(msg)); 
      } /* if the client is connected */
    } /* if the client is valid */
      /* Display the IP Address on the Screen. */
  display.stopscroll();    
  display.clearDisplay();

  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0,0);
  display.print((WiFi.localIP()));
  display.print(":");
  display.print(port);
  display.display();
  delay(100);
}

/* WIFI SERVER SECTION */
boolean recvWithStartEndMarkers(WiFiClient *client, char buff[STRLEN]){
    static boolean recvInProgress = false;
    static unsigned char ndx = 0; /* Requires that the stringlen is > 256 */ 
    boolean newData = false;
    char startMarker = '<';
    char endMarker = '>';
    char rc;
    int i;
 
    while (client->available() > 0 && newData == false) {
        rc = client->read();

        if (recvInProgress == true) {
            if (rc != endMarker) {
                buff[ndx] = rc;
                ndx++; /* ndx will wrap to 0 */
            }
            else {
                buff[ndx] = '\0'; // terminate the string
                recvInProgress = false;
                newData = true;
                ndx=0;
            }
        }

        else if (rc == startMarker) {
            recvInProgress = true;
        }
    }
    return newData;
}
void check_client_data(){
  static char line[STRLEN]={0};
    if(wifiClient){
      if(wifiClient.connected() && wifiClient.available()){
        if(recvWithStartEndMarkers(&wifiClient, line)){
          if(strstr(line,"reset"))
            send_reset_to_timer();
          else if(strstr(line,"counts"))
            wifiClient.write((uint8_t *)&counts,sizeof(counts));
          else{
        //      Serial.println("TODO: figure out how to handle that string!");
            }
        } /* if we read something */
      } /* if the client is connected and has data for us. */
    } /* if the client exists */
}/* print_client_data()*/
void on_wifi_disconnected(const WiFiEventStationModeDisconnected& event){
  /* Make sure and close all open clients so that their spots are cleared. */
 // Serial.print("Wifi disconnected. Closing all open TCP clients.\n");
    if(wifiClient){
      wifiClient.stop();
    }
}
void check_for_disconnected_clients(){
  /* Check for disconnected clients */
    if(client_connected && !wifiClient.connected()){
      wifiClient.stop();
      client_connected=false;
   //   Serial.print("Client Disconnected.\n");
    }
}
void handle_new_client(){
    /*find free/disconnected spot*/
    if (!wifiClient || !wifiClient.connected()) {
      if (wifiClient) wifiClient.stop();
      wifiClient = wifiServer.available();
   //   Serial.print("New client.\n");
      client_connected=true;
    }
  else{/* Reject*/
    WiFiClient serverClient = wifiServer.available();
    serverClient.stop();
  }
}
/* WIFI SERVER SECTION */

void loop() {
   
  if(wifiServer.hasClient()){
    handle_new_client();
  }

  if(digitalRead(RESET_IN))
    reset_pressed=0;
  else if(!reset_pressed)
    reset_rx();

  check_for_disconnected_clients();
  
  /* If the race is running, then check results. */
  if(is_set){
    check_timer();
  }

  /* Update the values so we can detect when the race starts. */
  last_val = counts;

  /* Check for any data that was sent so we clear the buffer. */
  check_client_data();

  if(!digitalRead(USER_INPUT)){
    press_count ++;
    switch(press_count){
      case 5: /* Reset the track */
        if(!reset_pressed)
          send_reset_to_timer();
          break;
      case 10: /* Three slow and three fast blinks */
      case 50:
      case 90:
      case 130:
      case 140:
      case 150:
        digitalWrite(LED_PIN,1);
        break;
      case 40:
      case 80:
      case 120:
      case 135:       
      case 145:
        digitalWrite(LED_PIN,0);
        break;
      case 155: /* Final blink, shutdown */
        digitalWrite(LED_PIN,0);
        cut_power();
      default:
        break;        
    }
  }
  else{
    press_count = 0;
    digitalWrite(LED_PIN,(i%current_rate)!=0);
  }

  i++;
  
  delay(LOOP_DELAY);  
}
