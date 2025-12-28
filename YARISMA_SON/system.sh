#!/bin/bash

# Open new terminal windows and run each Python script
gnome-terminal --tab --title="image_processor.py" --command="bash -c 'python3 image_processor.py; exec $SHELL'" \
--tab --title="coord_finder.py" --command="bash -c 'python3 kordinatfaynder.py; exec $SHELL'" \
--tab --title="mappingPattern.py" --command="bash -c 'python3 mappingPattern.py; exec $SHELL'" \
