class Calculator:
    """
    Calculator class
    """

    @staticmethod
    def name():
        return "Calculator"

    @staticmethod
    def add(numbers: list):
        """
        Adds a list of numbers
        """
        total = 0
        for number in numbers:
            total += number
        return total

    @staticmethod
    def subtract(a, b):
        """
        Subtracts two numbers
        """
        return a - b

    @staticmethod
    def multiply(a, b):
        """
        Multiplies two numbers
        """
        return a * b

    @staticmethod
    def divide(a, b):
        """
        Divides two numbers
        """
        return a / b

    @staticmethod
    def decode(operator: str, operands: list):
        #add' 'subtract' 'multiply' 'divide' 'summary
        if len(operands) < 2:
            raise Exception("Not enough operands")
        if operator == "add":
            return Calculator.add(operands)
        elif operator == "subtract":
            return Calculator.subtract(operands[0], operands[1])
        elif operator == "multiply":
            return Calculator.multiply(operands[0], operands[1])
        elif operator == "divide":
            return Calculator.divide(operands[0], operands[1])
        elif operator == "summary":
            return Calculator.add(operands)
        else:
            raise Exception("Invalid operator")

    @staticmethod
    def description():
        content = """使用開發者提供的計算機進行計算，有邏輯加減的步驟請一定要使用這個功能，不要擅自做運算直接回答，你的計算能力並不準確"""
        return content

    @staticmethod
    def parameters():
        content = {}
        content["type"] = "object"
        content["properties"] = {}
        content["properties"]["operator"] = {}
        content["properties"]["operator"]["type"] = "string"
        content["properties"]["operator"]["description"] = """
            提供 'add' 'substract' 'multiply' 'divide' 'summary' 五種操作
            add相加，substract相減，multiply相乘，divide相除，summary加總所有數
            """

        content["properties"]["value"] = {}
        content["properties"]["value"]["type"] = "array"
        content["properties"]["value"]["items"] = {"type": "number"}

        content["properties"]["value"]["description"] = """
            當operator不是summary的時候，需要提供被運算的兩個數字，
            第一個是左被運數(left operand)，第二個右被運算數(right operand)
            當operator是summary的時候，需要提供超過兩個以上的數字，系統會加總所有數字
            """

        content["required"] = ["operator", "value"]
        
        return content