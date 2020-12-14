# DotTrack

DotTrack is a system for tracking the 2D position of tangible blocks and their spatial relations developed at the junior research group [Physical-Digital Affordances at the University of Regensburg, Germany](https://hci.ur.de/). 
It allows tangible objects to track their own position on a surface using an off-the-shelf optical mouse sensor.
In addition to measuring the (relative) movement of the device, the sensor also allows capturing a low-resolution raw image of the surface. 
This makes it possible to detect the absolute position of the device via marker patterns at known positions.
Knowing the absolute position may either be used to trigger actions or as a known reference point for tracking the device.

DotTrack consists of a *shield/backplate* for the [M5Stack](http://www.m5stack.com/) blocks which contains a PixArt PMW3360 mouse sensor, a set of demo applications, and an implementation of position tracking via 2D patterns based on de-Bruijn sequences.

As the processing of sensor images and decodig of their position happens on an external host computer, the software is split up between a program for the M5Stack and a program for the host computer.
The devices communicate with each other over WiFi.

More information can be found on the [DotTrack project page](https://hci.ur.de/projects/dottrack).

## Table of Contents

 * *DotTrack:* Code for the M5Stack microcontroller which includes communication with the PMW3360 mouse sensor, streaming of raw images an position data to a host PC, and demo applications.
 * *auto_capture:* Code to automatically record sets of raw sensor images with a robotic arm.
 * *data_sets:* Sets of raw images of the pattern printed on different types of paper.
 * *dbt:* The tracking pattern used for DotTrack.
 * *legacy:* Legacy code that emerged during the development of DotTrack.
 * *live_tracker:* Program for the host PC. It receives raw sensor images, processes them, decodes the position, and sends it back to the microcontroller. Includes a debug view.
