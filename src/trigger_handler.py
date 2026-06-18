import time
try:
    from gpiozero import DigitalInputDevice, DigitalOutputDevice
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    class MockGPIO:
        def __init__(self, *args, **kwargs):
            self.when_activated = None
        def on(self): pass
        def off(self): pass
    DigitalInputDevice = MockGPIO
    DigitalOutputDevice = MockGPIO


class TriggerHandler:
    """
    Handles two GPIO inputs from the UR10e Robot Arm:
      1. Capture trigger   (BCM input_pin)  — take a photo
      2. Product done      (BCM done_pin)   — cycle finished, move to next product
    And one GPIO output:
      1. Capture confirm   (BCM output_pin) — photo saved, robot may move
    """
    def __init__(self, input_pin: int, output_pin: int, done_pin: int,
                 capture_callback, product_done_callback):
        """
        Args:
            input_pin (int):            BCM pin for capture trigger from UR10e.
            output_pin (int):           BCM pin for confirmation pulse back to UR10e.
            done_pin (int):             BCM pin for product-done signal from UR10e.
            capture_callback:           Called when a capture trigger fires. Returns bool.
            product_done_callback:      Called when the product-done signal fires.
        """
        # Both inputs use pull_up=False (pull-down to GND when idle)
        # bounce_time=0.25 gives 250ms debounce, equivalent to Arduino debounce pattern
        self.trigger_input = DigitalInputDevice(input_pin, pull_up=False, bounce_time=0.25)
        self.done_input    = DigitalInputDevice(done_pin,  pull_up=False, bounce_time=0.25)
        self.confirmation_output = DigitalOutputDevice(output_pin)

        self.capture_callback      = capture_callback
        self.product_done_callback = product_done_callback

        # Bind rising edge events
        self.trigger_input.when_activated = self._handle_capture_trigger
        self.done_input.when_activated    = self._handle_product_done

    def _handle_capture_trigger(self):
        """Executed in gpiozero background thread when capture pin goes HIGH."""
        success = self.capture_callback()
        if success:
            self._send_confirmation()

    def _handle_product_done(self):
        """Executed in gpiozero background thread when product-done pin goes HIGH."""
        self.product_done_callback()

    def _send_confirmation(self):
        """Send a 100ms HIGH pulse back to the UR10e to signal image saved."""
        self.confirmation_output.on()
        time.sleep(0.1)   # 100ms — reliably detectable by UR10e (scan cycle = 8ms)
        self.confirmation_output.off()
