# DotTrack

DotTrack is a system for tracking the 2D position of tangible blocks and their spatial relations. 
It allows tangible objects to track their own position on a surface using an off-the-shelf optical mouse sensor.
In addition to measuring the (relative) movement of the device, the sensor also allows capturing a low-resolution raw image of the surface. 
This makes it possible to detect the absolute position of the device via marker patterns at known positions.
Knowing the absolute position may either be used to trigger actions or as a known reference point for tracking the device.

DotTrack consists of a *shield/backplate* for the [M5Stack](http://www.m5stack.com/) blocks which contains a PixArt PMW3360 mouse sensor, a set of demo applications (this repository), and a (work-in-progress) implementation of position tracking via 2D patterns based on de-Bruijn sequences.

More information can be found on the [DotTrack project page](https://hci.ur.de/projects/dottrack).
