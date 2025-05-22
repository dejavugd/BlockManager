from .gui import BlockManagerGUI

class BlockManager:
    def __init__(self):
        self.app = BlockManagerGUI()
        self.app.mainloop()