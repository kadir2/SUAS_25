#!/bin/bash

# Open new terminal windows and run each Python script
gnome-terminal --tab --title="image_processor.py" --command="bash -c 'python3 image_processor.py; exec $SHELL'" \
--tab --title="coord_finder.py" --command="bash -c 'python3 coord_finder.py; exec $SHELL'" \
--tab --title="mappingson.py" --command="bash -c 'python3 mappingson.py; exec $SHELL'" \
