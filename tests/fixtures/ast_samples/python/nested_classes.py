class Outer:
    class Inner:
        def inner_method(self):
            pass

    def create_closure(self):
        captured = 10

        def closure_func():
            return captured

        return closure_func

    def processor(self, x):
        return x * 2
