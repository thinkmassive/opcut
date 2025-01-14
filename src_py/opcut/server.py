from pathlib import Path
import asyncio
import subprocess
import sys

from hat import aio
from hat import json
import aiohttp.web

from opcut import common


static_dir: Path = common.package_path / 'ui'


async def create(host: str,
                 port: int
                 ) -> 'Server':
    server = Server()
    server._async_group = aio.Group()
    server._executor = aio.create_executor()

    app = aiohttp.web.Application()
    app.add_routes([
        aiohttp.web.get('/', server._root_handler),
        aiohttp.web.post('/calculate', server._calculate_handler),
        aiohttp.web.post('/generate_output', server._generate_output_handler),
        aiohttp.web.static('/', static_dir)])

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    server.async_group.spawn(aio.call_on_cancel, runner.cleanup)

    try:
        site = aiohttp.web.TCPSite(runner=runner,
                                   host=host,
                                   port=port,
                                   shutdown_timeout=0.1,
                                   reuse_address=True)
        await site.start()

    except BaseException:
        await aio.uncancellable(server.async_close())
        raise

    return server


class Server(aio.Resource):

    @property
    def async_group(self):
        return self._async_group

    async def _root_handler(self, request):
        raise aiohttp.web.HTTPFound('/index.html')

    async def _calculate_handler(self, request):
        try:
            data = await request.json()
            common.json_schema_repo.validate(
                'opcut://opcut.yaml#/definitions/params', data)

        except Exception:
            return aiohttp.web.Response(status=400,
                                        text="Invalid request")

        native = request.query.get('native') == 'true'
        method = common.Method(request.query['method'])
        params = common.params_from_json(data)

        try:
            result = await _calculate(native, method, params)
            return aiohttp.web.json_response(result)

        except common.UnresolvableError:
            return aiohttp.web.Response(status=400,
                                        text='Result is not solvable')

    async def _generate_output_handler(self, request):
        try:
            data = await request.json()
            common.json_schema_repo.validate(
                'opcut://opcut.yaml#/definitions/result', data)

        except Exception:
            return aiohttp.web.Response(status=400,
                                        text="Invalid request")

        output_type = common.OutputType(request.query['output_type'])
        panel = request.query.get('panel')
        result = common.result_from_json(data)

        output = await _generate_output(output_type, panel, result)

        if output_type == common.OutputType.PDF:
            content_type = 'application/pdf'

        elif output_type == common.OutputType.SVG:
            content_type = 'image/svg+xml'

        else:
            raise Exception('unsupported output type')

        return aiohttp.web.Response(body=output,
                                    content_type=content_type)


async def _calculate(native, method, params):
    args = [*_get_calculate_cmd(native), '--method', method.value]
    stdint_data = json.encode(common.params_to_json(params)).encode('utf-8')

    p = await asyncio.create_subprocess_exec(*args,
                                             stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
    stdout_data, stderr_data = await p.communicate(stdint_data)

    if p.returncode == 0:
        return json.decode(stdout_data.decode('utf-8'))

    if p.returncode == 42:
        raise common.UnresolvableError()

    raise Exception(stderr_data.decode('utf-8'))


async def _generate_output(output_type, panel, result):
    args = [*_get_generate_output_cmd(), '--output-type', output_type.value,
            *(['--panel', panel] if panel else [])]
    stdint_data = json.encode(common.result_to_json(result)).encode('utf-8')

    p = await asyncio.create_subprocess_exec(*args,
                                             stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
    stdout_data, stderr_data = await p.communicate(stdint_data)

    if p.returncode == 0:
        return stdout_data

    raise Exception(stderr_data.decode('utf-8'))


def _get_calculate_cmd(native):
    if native and sys.platform == 'linux':
        return [str(common.package_path / 'bin/linux-opcut-calculate')]

    elif native and sys.platform == 'win32':
        return [str(common.package_path / 'bin/windows-opcut-calculate.exe')]

    return [sys.executable, '-m', 'opcut', 'calculate']


def _get_generate_output_cmd():
    return [sys.executable, '-m', 'opcut', 'generate-output']
