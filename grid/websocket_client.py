import binascii
import time
from typing import List
from typing import Union

import socketio
import torch

import syft as sy
from syft.frameworks.torch.tensors.interpreters import AbstractTensor
from syft.workers import BaseWorker


class WebsocketGridClient(BaseWorker):
    """ Websocket Grid Client """

    def __init__(
        self,
        hook,
        addr: str,
        id: Union[int, str] = 0,
        is_client_worker: bool = False,
        log_msgs: bool = False,
        verbose: bool = False,
        data: List[Union[torch.Tensor, AbstractTensor]] = None,
    ):
        """
        Args:
            hook : a normal TorchHook object
            addr : the address this client connects to
            id : the unique id of the worker (string or int)
            log_msgs : whether or not all messages should be
                saved locally for later inspection.
            verbose : a verbose option - will print all messages
                sent/received to stdout
            data : any initial tensors the server should be
                initialized with (such as datasets)
        """
        self.uri = addr
        self.response_from_client = None
        self.wait_for_client_event = False

        # Creates the connection with the server
        self.sio = socketio.Client()
        super().__init__(hook, id, data, is_client_worker, log_msgs, verbose)

        @self.sio.on("/identity/")
        def check_identity(msg):
            if msg != "OpenGrid":
                raise PermissionError("App is not an OpenGrid app")

        @self.sio.on("/cmd")
        def on_client_result(args):
            if log_msgs:
                print("Receiving result from client {}".format(args))
            # The server broadcasted the results from another client
            self.response_from_client = binascii.unhexlify(args[2:-1])
            # Tell the wait_for_client_event to clear up and continue execution
            self.wait_for_client_event = False

    def _send_msg(self, message: bin) -> bin:
        raise NotImplementedError

    def _recv_msg(self, message: bin) -> bin:
        message = str(binascii.hexlify(message))
        # Sends the message to the server
        self.sio.emit("/cmd", {"message": message})

        self.wait_for_client_event = True
        # Wait until the server gets back with a result or an ACK
        while self.wait_for_client_event:
            time.sleep(0.1)

        # Return the result
        if self.response_from_client == "ACK":
            # Empty result for the serialiser to continue
            return sy.serde.serialize(b"")
        return self.response_from_client

    def connect(self):
        self.sio.connect(self.uri)

    def disconnect(self):
        self.sio.disconnect()