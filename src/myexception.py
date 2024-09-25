
class FlowException(Exception):
    def __init__(self, message="流程錯誤，請聯絡開發者"):
        # 調用父類別的初始化方法
        super().__init__(message)

class EarlyReturn(Exception):
    def __init__(self, message="程式區段被提早返回"):
        # 調用父類別的初始化方法
        super().__init__(message)

class ProgramError(Exception):
    def __init__(self, message="程式中有部分函數發生錯誤"):
        # 調用父類別的初始化方法
        super().__init__(message)