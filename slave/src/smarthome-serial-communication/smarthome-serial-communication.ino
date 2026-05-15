/*
   ______            __                  _            __                __________
  / ____/_  ______ _/ /__________ _   __(_)__  ____  / /_____  _____   / ____/  _/
 / /   / / / / __ `/ __/ ___/ __ \ | / / / _ \/ __ \/ __/ __ \/ ___/  / /    / /  
/ /___/ /_/ / /_/ / /_/ /  / /_/ / |/ / /  __/ / / / /_/ /_/ (__  )  / /____/ /   
\____/\__,_/\__,_/\__/_/   \____/|___/_/\___/\_/ /_/\__/\____/____/   \____/___/   
                                                                                
    __             ___              __             ______   __   
   / /_  __  __   /   |  ____  ____/ /__  _____   / ____/  / /   
  / __ \/ / / /  / /| | / __ \/ __  / _ \/ ___/  / /_     / /    
 / /_/ / /_/ /  / ___ |/ / / / /_/ /  __/ /     / __/  _ / /____ 
/_.___/\__, /  /_/  |_/_/ /_/\__,_/\___/\_/     /_/    (_)_____(_)
      /____/   
                                           
 Smarthome Serial Communication Project
 
 This project integrates all the smarthome lessons into a single Arduino sketch.
 It uses Serial communication for requests and results.

 CopyRight Ander F.L. <ander_frago@cuatrovientos.org> June 2024
*/

// Included Libraries
#include <LiquidCrystal_I2C.h>
#include <Servo.h>
#include <SPI.h>
#include <RFID.h>
#include <dht.h>
#include <Keypad.h>

// Pin Definitions
#define redLED 13
#define greenLED 12
#define buzzer 5
#define flame_sensor A1
#define sound_sensor A2
#define motion_sensor 4
#define whiteLED 9
#define yellowLED 10
#define Trig_PIN 25
#define Echo_PIN 26
#define SERVO_PIN 3
#define RFID_SDA 48
#define RFID_RST 49
#define DHT11_PIN 2
#define redPin_RGB 24
#define greenPin_RGB 23
#define bluePin_RGB 22

int rgb_r = 0;
int rgb_g = 0;
int rgb_b = 0;

// LCD Display
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Servo Motor
Servo head;

// RFID
unsigned char my_rfid[] = {227, 10, 252, 39, 50}; // replace with your RFID value
RFID rfid(RFID_SDA, RFID_RST);

// DHT Sensor
dht DHT;

// Keypad
const byte ROWS = 4;
const byte COLS = 4;
char hexaKeys[ROWS][COLS] = {
  {'1', '2', '3', 'A'},
  {'4', '5', '6', 'B'},
  {'7', '8', '9', 'C'},
  {'*', '0', '#', 'D'}
};
byte rowPins[ROWS] = {33, 35, 37, 39};
byte colPins[COLS] = {41, 43, 45, 47};
Keypad customKeypad = Keypad(makeKeymap(hexaKeys), rowPins, colPins, ROWS, COLS);

String command = "";
String rgb_color = "off";

void setup() {
  // Initialize Serial
  Serial.begin(9600);
  command.reserve(256);

  // Initialize Pins
  pinMode(redLED, OUTPUT);
  pinMode(greenLED, OUTPUT);
  pinMode(buzzer, OUTPUT);
  pinMode(flame_sensor, INPUT);
  pinMode(sound_sensor, INPUT);
  pinMode(motion_sensor, INPUT);
  pinMode(whiteLED, OUTPUT);
  pinMode(yellowLED, OUTPUT);
  pinMode(Trig_PIN, OUTPUT);
  pinMode(Echo_PIN, INPUT);
  pinMode(redPin_RGB, OUTPUT);
  pinMode(greenPin_RGB, OUTPUT);
  pinMode(bluePin_RGB, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.print("Smarthome Ready!");

  // Initialize SPI and RFID
  SPI.begin();
  rfid.init();

  Serial.println("Smarthome Ready. Enter commands via Serial monitor.");
}

void loop() {
  // Handle Serial Commands
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      executeCommand(command);
      command = "";
    } else {
      command += c;
    }
  }

  // Handle Keypad Input
  handleKeypad();
  
  // Handle RFID
  handleRFID();
}

void executeCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  Serial.print("Executing command: ");
  Serial.println(cmd);

  if (cmd.startsWith("led")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(LED_BUILTIN, HIGH);
      Serial.println("Result: LED is ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(LED_BUILTIN, LOW);
      Serial.println("Result: LED is OFF");
    }
  } else if (cmd.startsWith("rgb:")) {
    int r, g, b;
    if (sscanf(cmd.c_str(), "rgb: %d, %d, %d", &r, &g, &b) == 3) {

      r = constrain(r, 0, 255);
      rgb_r = r;
      g = constrain(g, 0, 255);
      rgb_g = g;
      b = constrain(b, 0, 255);
      rgb_b = b;

      color(r, g, b);

      Serial.print("Result: RGB set to ");
      Serial.print(r);
      Serial.print(", ");
      Serial.print(g);
      Serial.print(", ");
      Serial.println(b);

    } else {
      Serial.println("Error: Use format -> rgb: 255, 20, 100");
    }
} else if (cmd.startsWith("buzzer")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(buzzer, HIGH);
      Serial.println("Result: Buzzer is ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(buzzer, LOW);
      Serial.println("Result: Buzzer is OFF");
    }
  } else if (cmd.startsWith("sensors")) {
    readAllSensors();
  } else if (cmd.startsWith("servo")) {
      if (cmd.indexOf("open") > 0) {
        open_door();
        Serial.println("Result: Servo OPEN");
      } else if (cmd.indexOf("half") > 0) {
        half_open();
        Serial.println("Result: Servo HALF-OPEN");
      } else if (cmd.indexOf("close") > 0) {
        close_door();
        Serial.println("Result: Servo CLOSE");
      }
  } else if (cmd.startsWith("lcd")) {
      int firstQuote = cmd.indexOf('"');
      int secondQuote = cmd.lastIndexOf('"');
      if (firstQuote != -1 && secondQuote != -1 && firstQuote != secondQuote) {
        String msg = cmd.substring(firstQuote + 1, secondQuote);
        lcd.clear();
        lcd.backlight();
        lcd.print(msg);
        Serial.println("Result: LCD message sent");
      }
  } else if (cmd.startsWith("red")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(redLED, HIGH);
      Serial.println("Result: LED Rojo ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(redLED, LOW);
      Serial.println("Result: LED Rojo OFF");
    }
  } else if (cmd.startsWith("green")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(greenLED, HIGH);
      Serial.println("Result: LED Verde ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(greenLED, LOW);
      Serial.println("Result: LED Verde OFF");
    }
  } else if (cmd.startsWith("yellow")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(yellowLED, HIGH);
      Serial.println("Result: LED Amarillo ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(yellowLED, LOW);
      Serial.println("Result: LED Amarillo OFF");
    }
  } else if (cmd.startsWith("white")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(whiteLED, HIGH);
      Serial.println("Result: Luz Exterior ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(whiteLED, LOW);
      Serial.println("Result: Luz Exterior OFF");
    }
  } else if (cmd.startsWith("lights")) {
    if (cmd.indexOf("on") > 0) {
      digitalWrite(redLED, HIGH);
      digitalWrite(greenLED, HIGH);
      digitalWrite(yellowLED, HIGH);
      digitalWrite(whiteLED, HIGH);
      color(255, 255, 255);
      rgb_color = "white";
      Serial.println("Result: Todas las luces ON");
    } else if (cmd.indexOf("off") > 0) {
      digitalWrite(redLED, LOW);
      digitalWrite(greenLED, LOW);
      digitalWrite(yellowLED, LOW);
      digitalWrite(whiteLED, LOW);
      color(0, 0, 0);
      rgb_color = "off";
      Serial.println("Result: Todas las luces OFF");
    }
  } else {
    Serial.println("Unknown command");
  }
}

void readAllSensors() {
  // Flame Sensor
  int flame_status = digitalRead(flame_sensor);
  if (flame_status == 1) {
    Serial.println("Result: Safe (No Fire)");
  } else {
    Serial.println("Result: Fire Detected!");
  }

  // Sound Sensor
  int SoundStatus = digitalRead(sound_sensor);
  if (SoundStatus == 1) {
    Serial.println("Result: No Noise!");
  } else {
    Serial.println("Result: Noise Detected!");
  }

  // Motion Sensor
  int gasStatus = digitalRead(motion_sensor);
  if (gasStatus == 0) {
    Serial.println("Result: No Intruder!");
  } else {
    Serial.println("Result: Intruder Detected!");
  }

  // Ultrasonic Sensor
  int distance_val = watch();
  Serial.print("Result: Distance: ");
  Serial.print(distance_val);
  Serial.println(" cm");

  // DHT11 Sensor
  DHT.read11(DHT11_PIN);
  Serial.print("Result: Humidity: ");
  Serial.print(DHT.humidity, 1);
  Serial.println("%");
  Serial.print("Result: Temperature: ");
  Serial.print(DHT.temperature, 1);
  Serial.println("C");

  // Estado de las luces
  Serial.print("Result: red LED: ");
  Serial.println(digitalRead(redLED) ? "ON" : "OFF");
  Serial.print("Result: green LED: ");
  Serial.println(digitalRead(greenLED) ? "ON" : "OFF");
  Serial.print("Result: yellow LED: ");
  Serial.println(digitalRead(yellowLED) ? "ON" : "OFF");
  Serial.print("Result: white LED: ");
  Serial.println(digitalRead(whiteLED) ? "ON" : "OFF");
  Serial.print("Result: RGB status: ");
  Serial.println(rgb_color);
  Serial.print("Result: RGB color: ");
  Serial.println(String(rgb_r) + ", " + String(rgb_g) + ", " + String(rgb_b));
}

void handleKeypad() {
  char customKey = customKeypad.getKey();
  if (customKey == '*') {
    close_door();
    Serial.println("Keypad: Door Closed");
  }
  if (customKey == '#') {
    open_door();
    Serial.println("Keypad: Door Opened");
  }
  if (customKey == '0') {
    half_open();
    Serial.println("Keypad: Door Half-Opened");
  }
}

void handleRFID() {
  if (rfid.isCard()) {
    if (rfid.readCardSerial()) {
      if (compare_rfid(rfid.serNum, my_rfid)) {
        open_door();
        Serial.println("RFID: Access Granted");
      } else {
        close_door();
        digitalWrite(buzzer, HIGH);
        delay(1000);
        digitalWrite(buzzer, LOW);
        Serial.println("RFID: Access Denied");
      }
    }
    rfid.halt();
  }
}

// Helper functions
void color(unsigned char red, unsigned char green, unsigned char blue) {
  analogWrite(redPin_RGB, red);
  analogWrite(greenPin_RGB, green);
  analogWrite(bluePin_RGB, blue);
}

void open_door() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(180);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, HIGH);
  digitalWrite(redLED, LOW);
}

void half_open() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(90);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, LOW);
  digitalWrite(redLED, LOW);
}

void close_door() {
  head.attach(SERVO_PIN);
  delay(300);
  head.write(0);
  delay(400);
  head.detach();
  digitalWrite(SERVO_PIN, LOW);
  digitalWrite(greenLED, LOW);
  digitalWrite(redLED, HIGH);
}

boolean compare_rfid(unsigned char x[], unsigned char y[]) {
  for (int i = 0; i < 5; i++) {
    if (x[i] != y[i]) return false;
  }
  return true;
}

int watch() {
  long echo_distance;
  digitalWrite(Trig_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(Trig_PIN, HIGH);
  delayMicroseconds(15);
  digitalWrite(Trig_PIN, LOW);
  echo_distance = pulseIn(Echo_PIN, HIGH);
  echo_distance = echo_distance * 0.01657;
  return round(echo_distance);
}
