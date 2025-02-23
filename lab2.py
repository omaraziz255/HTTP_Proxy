# Don't forget to change this file's name before submission.
import sys
import os
import enum
import socket
import threading

cache = dict()


class HttpRequestInfo(object):
    """
    Represents a HTTP request information
    Since you'll need to standardize all requests you get
    as specified by the document, after you parse the
    request from the TCP packet put the information you
    get in this object.
    To send the request to the remote server, call to_http_string
    on this object, convert that string to bytes then send it in
    the socket.
    client_address_info: address of the client;
    the client of the proxy, which sent the HTTP request.
    requested_host: the requested website, the remote website
    we want to visit.
    requested_port: port of the webserver we want to visit.
    requested_path: path of the requested resource, without
    including the website name.
    NOTE: you need to implement to_http_string() for this class.
    """

    def __init__(self, client_info, method: str, requested_host: str,
                 requested_port: int,
                 requested_path: str,
                 headers: list):
        self.method = method
        self.client_address_info = client_info
        self.requested_host = requested_host
        self.requested_port = requested_port
        self.requested_path = requested_path
        # Headers will be represented as a list of lists
        # for example ["Host", "www.google.com"]
        # if you get a header as:
        # "Host: www.google.com:80"
        # convert it to ["Host", "www.google.com"] note that the
        # port is removed (because it goes into the request_port variable)
        self.headers = headers

    def to_http_string(self):
        """
        Convert the HTTP request/response
        to a valid HTTP string.
        As the protocol specifies:
        [request_line]\r\n
        [header]\r\n
        [headers..]\r\n
        \r\n
        (just join the already existing fields by \r\n)
        You still need to convert this string
        to byte array before sending it to the socket,
        keeping it as a string in this stage is to ease
        debugging and testing.
        """

        string = f"{self.method} {self.requested_path} HTTP/1.0\r\n"
        for h in self.headers:
            string += f"{h[0]}: {h[1]}\r\n"
        string += "\r\n"

        return string

    def to_byte_array(self, http_string):
        """
        Converts an HTTP string to a byte array.
        """
        return bytes(http_string, "UTF-8")

    def display(self):
        print(f"Client:", self.client_address_info)
        print(f"Method:", self.method)
        print(f"Host:", self.requested_host)
        print(f"Port:", self.requested_port)
        stringified = [": ".join([k, v]) for (k, v) in self.headers]
        print("Headers:\n", "\n".join(stringified))


class HttpErrorResponse(object):
    """
    Represents a proxy-error-response.
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message

    def to_http_string(self):
        return f"{self.message} ({self.code})\n"

    def to_byte_array(self, http_string):
        """
        Converts an HTTP string to a byte array.
        """
        return bytes(http_string, "UTF-8")

    def display(self):
        print(self.to_http_string())


class HttpRequestState(enum.Enum):
    """
    The values here have nothing to do with
    response values i.e. 400, 502, ..etc.
    Leave this as is, feel free to add yours.
    """
    INVALID_INPUT = 0
    NOT_SUPPORTED = 1
    GOOD = 2
    PLACEHOLDER = -1


def generateError(state):
    if state == HttpRequestState.INVALID_INPUT:
        return HttpErrorResponse(400, "Bad Request")
    else:
        return HttpErrorResponse(501, "Not Implemented")


def entry_point(proxy_port_number):
    """
    Entry point, start your code here.
    Please don't delete this function,
    but feel free to modify the code
    inside it.
    """

    proxy = setup_sockets(int(proxy_port_number))
    do_socket_logic(proxy)


def setup_sockets(proxy_port_number):
    """
    Socket logic MUST NOT be written in the any
    class. Classes know nothing about the sockets.
    But feel free to add your own classes/functions.
    Feel free to delete this function.
    """
    print("Starting HTTP proxy on port:", proxy_port_number)
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.bind(("localhost", proxy_port_number))
    proxy_socket.listen(20)
    # when calling socket.listen() pass a number
    # that's larger than 10 to avoid rejecting
    # connections automatically.
    return proxy_socket


def do_socket_logic(socket):
    """
    Example function for some helper logic, in case you
    want to be tidy and avoid stuffing the main function.
    Feel free to delete this function.
    """
    while True:
        client, address = socket.accept()
        thread = threading.Thread(target=clientHandler, args=(client, address))
        thread.start()


def clientHandler(client, address):
    request = ""
    count = 0
    while request.find("\r\n\r\n") == -1 and count < 5:
        received = client.recv(2 ** 10)
        request += received.decode("unicode_escape")
        count += 1
    response = http_request_pipeline(address, request)
    if isinstance(response, HttpErrorResponse):
        client.sendto(response.to_byte_array(response.to_http_string()), address)
    else:
        r = checkCache(response)
        if r is None:
            r = fetchServer(response)
            cacheRequest(response, r)
        if r is not None:
            if isinstance(r, list):
                for response in r:
                    client.sendto(response, address)
            else:
                client.sendto(r, address)
    client.close()


def checkCache(response):
    url = response.requested_host + response.requested_path
    if url in cache.keys():
        return cache[url]
    else:
        return None


def cacheRequest(response, r):
    if response != bytes("Unresolved Host", "UTF-8") and response != bytes("Request took too much time", "UTF-8"):
        cache[response.requested_host + response.requested_path] = r


def fetchServer(response):
    data = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        IP = socket.gethostbyname(response.requested_host)
    except Exception:
        return bytes("Unresolved Host", "UTF-8")
    try:
        server.connect((IP, response.requested_port))
    except TimeoutError:
        return bytes("Request took too much time", "UTF-8")
    server.send(response.to_byte_array(response.to_http_string()))
    received_data = server.recv(2**15)
    while len(received_data) > 0:
        data.append(received_data)
        received_data = server.recv(2**15)
    server.close()
    return data


def http_request_pipeline(source_addr, http_raw_data):
    """
    HTTP request processing pipeline.
    - Validates the given HTTP request and returns
      an error if an invalid request was given.
    - Parses it
    - Returns a sanitized HttpRequestInfo
    returns:
     HttpRequestInfo if the request was parsed correctly.
     HttpErrorResponse if the request was invalid.
    Please don't remove this function, but feel
    free to change its content
    """
    # Parse HTTP request
    validity = check_http_request_validity(http_raw_data)
    if validity != HttpRequestState.GOOD:
        http = generateError(validity)
    else:
        http = parse_http_request(source_addr, http_raw_data)
        sanitize_http_request(http)
        http.display()
    # Return error if needed, then:
    # parse_http_request()
    # sanitize_http_request()
    # Validate, sanitize, return Http object.
    return http


def parse_http_request(source_addr, http_raw_data):
    """
    This function parses a "valid" HTTP request into an HttpRequestInfo
    object.
    """
    components = http_raw_data.split("\r\n")
    components = list(filter(None, components))
    methodPathVersion = components[0]
    method, path, version = methodPathVersion.split(" ")
    port, headers, requested_host = parse_headers(components[1:])
    # Replace this line with the correct values.
    ret = HttpRequestInfo(source_addr, method, requested_host, port, path.strip(), headers)
    return ret


def parse_headers(components):
    port = 80
    headers = []
    host = None
    for c in components:
        splits = c.split(": ")
        h = [splits[0].strip(), splits[1].strip()]
        headers.append(h)
        if h[0] == "Host":
            splits2 = h[1].split(":")
            host = splits2[0]
            if len(splits2) > 2:
                port = int(splits2[1])
    return port, headers, host


def check_http_request_validity(http_raw_data: str) -> HttpRequestState:
    """
    Checks if an HTTP request is valid
    returns:
    One of values in HttpRequestState
    """
    http_raw_data = http_raw_data.lower()
    correct = HttpRequestState.GOOD
    state = checkRequestLine(http_raw_data.split("\r\n")[0])
    if state != correct:
        return state
    headers = http_raw_data.split("\r\n")[1:]
    method = http_raw_data.split(" ")[0]
    path = http_raw_data.split(" ")[1]
    version = http_raw_data.split(" ")[2]
    state = checkCRLF(http_raw_data)
    if state != correct:
        return state
    state = checkHeaders(headers)
    if state != correct:
        return state
    state = resolveHost(path, headers)
    if state != correct:
        return state
    state = checkVersion(version)
    if state != correct:
        return state
    state = checkMethod(method)
    if state != correct:
        return state
    # return HttpRequestState.GOOD (for example)
    return correct


def checkCRLF(string):
    if string[-4:] != "\r\n\r\n":
        print("ERROR: CRLF")
        return HttpRequestState.INVALID_INPUT
    else:
        return HttpRequestState.GOOD


def resolveHost(path: str, headers):
    host = True
    if path.startswith("/"):
        host = False
        for h in headers:
            line = h.split(": ")
            if line[0].strip() == "host":
                host = True
    if host:
        return HttpRequestState.GOOD
    else:
        print("ERROR: Host")
        return HttpRequestState.INVALID_INPUT


def checkVersion(version: str):
    version = version.strip()[:version.find("\r\n")]
    if version != "http/1.0" and version != "http/1.1":
        print("ERROR: Version")
        return HttpRequestState.INVALID_INPUT
    else:
        return HttpRequestState.GOOD


def checkHeaders(headers):
    headers = list(filter(None, headers))
    if headers is None or len(headers) == 0:
        return HttpRequestState.GOOD
    for h in headers:
        line = h.split(": ")
        if (len(line) < 2) or (len(line) > 3):
            print("ERROR: Headers")
            return HttpRequestState.INVALID_INPUT
        elif len(line) == 3:
            if (line[0].strip() != "host") or not(str.isnumeric(line[-1].strip())):
                print("ERROR: Headers2")
                return HttpRequestState.INVALID_INPUT
    return HttpRequestState.GOOD


def checkMethod(method):
    if method == "get":
        return HttpRequestState.GOOD
    elif method in ["put", "post", "delete", "head"]:
        return HttpRequestState.NOT_SUPPORTED
    else:
        print("ERROR: Method")
        return HttpRequestState.INVALID_INPUT


def checkRequestLine(request):
    if request is None or request == "":
        return HttpRequestState.INVALID_INPUT
    elif len(request.split(" ")) != 3:
        return HttpRequestState.INVALID_INPUT
    else:
        return HttpRequestState.GOOD


def sanitize_http_request(request_info: HttpRequestInfo):
    """
    Puts an HTTP request on the sanitized (standard) form
    by modifying the input request_info object.
    for example, expand a full URL to relative path + Host header.
    returns:
    nothing, but modifies the input object
    """
    path = request_info.requested_path
    if not(path.startswith("/")):
        if path.__contains__("http"):
            index = path.find("/", 8)
            index2 = path.find("//") + 2
            host = path[index2:index]
            relative = path[index:]
        else:
            index = path.find("/")
            if index == -1:
                host = path
                relative = "/"
            else:
                host = path[:index]
                relative = path[index:]
        if relative == "":
            relative = "/"
        if host.__contains__(":"):
            splits = host.split(":")
            splits = list(filter(None, splits))
            host = splits[0]
            port = int(splits[1])
            request_info.requested_port = port
        request_info.requested_path = relative
        if request_info.requested_host is None:
            request_info.headers.insert(0, ("Host", host))
            request_info.requested_host = host


#######################################
# Leave the code below as is.
#######################################


def get_arg(param_index, default=None):
    """
        Gets a command line argument by index (note: index starts from 1)
        If the argument is not supplies, it tries to use a default value.
        If a default value isn't supplied, an error message is printed
        and terminates the program.
    """
    try:
        return sys.argv[param_index]
    except IndexError as e:
        if default:
            return default
        else:
            print(e)
            print(
                f"[FATAL] The comand-line argument #[{param_index}] is missing")
            exit(-1)    # Program execution failed.


def check_file_name():
    """
    Checks if this file has a valid name for *submission*
    leave this function and as and don't use it. it's just
    to notify you if you're submitting a file with a correct
    name.
    """
    script_name = os.path.basename(__file__)
    import re
    matches = re.findall(r"(\d{4}_){,2}lab2\.py", script_name)
    if not matches:
        print(f"[WARN] File name is invalid [{script_name}]")
    else:
        print(f"[LOG] File name is correct.")


def main():
    """
    Please leave the code in this function as is.
    To add code that uses sockets, feel free to add functions
    above main and outside the classes.
    """
    print("\n\n")
    print("*" * 50)
    print(f"[LOG] Printing command line arguments [{', '.join(sys.argv)}]")
    check_file_name()
    print("*" * 50)

    # This argument is optional, defaults to 18888
    proxy_port_number = get_arg(1, 18888)
    entry_point(proxy_port_number)


if __name__ == "__main__":
    main()


