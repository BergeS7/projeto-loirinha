# Cloud Functions for Firebase (Python) - check-in de motoristas e telemetria.
# Deploy com `firebase deploy` (NÃO execute para os testes locais).

import os

import firebase_admin
from firebase_admin import db as rtdb
from firebase_admin import firestore, initialize_app
from firebase_functions import https_fn, scheduler_fn
from firebase_functions.options import set_global_options

import checkin
import fleet_routes
import telemetry

# For cost control, you can set the maximum number of containers that can be
# running at the same time. This helps mitigate the impact of unexpected
# traffic spikes by instead downgrading performance. This limit is a per-function
# limit. You can override the limit for each function using the max_instances
# parameter in the decorator, e.g. @https_fn.on_request(max_instances=5).
# Região de TODAS as functions (callable e agendada). Precisa bater com a região
# usada pelos clientes: httpsCallable(functions, ...) com
# getFunctions(app, "southamerica-east1") e as URLs do emulador
# (http://127.0.0.1:5001/<projeto>/southamerica-east1/<função>).
REGION = "southamerica-east1"
set_global_options(region=REGION, max_instances=10)

initialize_app()


@https_fn.on_call()
def checkIn(req: https_fn.CallableRequest) -> dict:
    """Motorista assume um ônibus. Entrada: {"tagCode": "TAG-BUS-01"}.

    O UID e a role vêm exclusivamente de `req.auth` (token verificado; a role
    é a custom claim `role`); qualquer "uid"/"role" enviado no payload é
    ignorado.
    """
    uid = req.auth.uid if req.auth is not None else None
    claims = req.auth.token if req.auth is not None else None
    try:
        return checkin.handle_check_in(firestore.client(), uid, req.data, claims)
    except checkin.CheckInError as err:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode(err.code),
            err.message,
            details={"reason": err.reason},
        )


@https_fn.on_call()
def checkOut(req: https_fn.CallableRequest) -> dict:
    """Fim de expediente: libera os ônibus do motorista autenticado.

    Não recebe payload: o UID e a role vêm exclusivamente de `req.auth`
    (token verificado; a role é a custom claim `role`). Só ônibus vinculados
    ao PRÓPRIO UID são liberados. Idempotente: sem ônibus vinculado devolve
    sucesso com `releasedBuses` vazio.
    """
    uid = req.auth.uid if req.auth is not None else None
    claims = req.auth.token if req.auth is not None else None
    try:
        return checkin.handle_check_out(firestore.client(), uid, claims)
    except checkin.CheckInError as err:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode(err.code),
            err.message,
            details={"reason": err.reason},
        )


# -------------------------------------------------------------------- rotas
def _run_route_handler(handler, req: https_fn.CallableRequest) -> dict:
    """UID e role vêm só de `req.auth` (token verificado); o payload nunca
    define identidade, frota ou role."""
    uid = req.auth.uid if req.auth is not None else None
    claims = req.auth.token if req.auth is not None else None
    try:
        return handler(firestore.client(), uid, req.data, claims)
    except fleet_routes.RouteError as err:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode(err.code),
            err.message,
            details={"reason": err.reason},
        )


@https_fn.on_call()
def createRoute(req: https_fn.CallableRequest) -> dict:
    """Dono da frota cadastra uma rota nova na PRÓPRIA frota (role `dono_frota`)."""
    return _run_route_handler(fleet_routes.handle_create_route, req)


@https_fn.on_call()
def setDriverRoute(req: https_fn.CallableRequest) -> dict:
    """Dono da frota atribui rota (da sua frota) a motorista (da sua frota).
    Entrada: {"driverId", "routeId"} (IDs de documentos)."""
    return _run_route_handler(fleet_routes.handle_set_driver_route, req)


@https_fn.on_call()
def getBusRoute(req: https_fn.CallableRequest) -> dict:
    """Dono da frota consulta a rota do motorista ativo de um ônibus seu.
    Entrada: {"busId"}."""
    return _run_route_handler(fleet_routes.handle_get_bus_route, req)


@https_fn.on_call()
def getMyRoute(req: https_fn.CallableRequest) -> dict:
    """Motorista (role `motorista`) lê a própria rota. Sem payload."""
    return _run_route_handler(fleet_routes.handle_get_my_route, req)


# ---------------------------------------------------------------- telemetria
def _telemetry_root():
    """Referência Admin SDK de /telemetry (Realtime Database).

    Em produção a URL vem de FIREBASE_CONFIG (databaseURL). No emulador, com
    FIREBASE_DATABASE_EMULATOR_HOST definido, o Admin SDK troca o host pela do
    emulador e usa o namespace `<projeto>-default-rtdb`.
    """
    app = firebase_admin.get_app()
    project = app.project_id or os.environ.get("GCLOUD_PROJECT", "")
    url = (app.options.get("databaseURL")
           or f"https://{project}-default-rtdb.firebaseio.com")
    return rtdb.reference("/telemetry", app=app, url=url)


def _as_https_error(err: "telemetry.TelemetryError") -> https_fn.HttpsError:
    return https_fn.HttpsError(
        https_fn.FunctionsErrorCode(err.code), str(err),
        details={"reason": err.reason})

@https_fn.on_call()
def sendTelemetry(req: https_fn.CallableRequest) -> dict:
    """Heartbeat do celular do ônibus (a cada ~15-20 s).

    Entrada: {"busId", "lat", "lng", "speed", "heading", "status",
    "captured_at"?}. UID e role vêm só de `req.auth`. O cliente NÃO escreve no
    RTDB: quem grava (e carimba `updated_at`) é esta Function.
    """
    uid = req.auth.uid if req.auth is not None else None
    claims = req.auth.token if req.auth is not None else None
    try:
        return telemetry.handle_send_telemetry(
            firestore.client(), _telemetry_root(), uid, req.data, claims)
    except telemetry.TelemetryError as err:
        raise _as_https_error(err)


@https_fn.on_call()
def endTelemetry(req: https_fn.CallableRequest) -> dict:
    """Fim normal da viagem: remove /telemetry/{busId} (não é perda de conexão)."""
    uid = req.auth.uid if req.auth is not None else None
    claims = req.auth.token if req.auth is not None else None
    try:
        return telemetry.handle_end_telemetry(
            firestore.client(), _telemetry_root(), uid, req.data, claims)
    except telemetry.TelemetryError as err:
        raise _as_https_error(err)


# Monitor de produção. O Cloud Scheduler NÃO tem emulador e o Functions
# Emulator não dispara funções agendadas sozinho; por isso, localmente, o
# monitor é o processo `scripts/telemetry_monitor.py`. Esta função só é
# registrada FORA do emulador (FUNCTIONS_EMULATOR != "true"), para não alterar
# o carregamento das Functions locais nem rodar monitor em duplicidade.
# Cloud Scheduler tem granularidade mínima de 1 min: cada execução faz 4
# varreduras com 15 s de intervalo (detecção em no máximo ~60 s de idade).
if os.environ.get("FUNCTIONS_EMULATOR") != "true":

    @scheduler_fn.on_schedule(schedule="* * * * *", timeout_sec=90)
    def monitorTelemetry(event: scheduler_fn.ScheduledEvent) -> None:
        telemetry.run_sweeps(
            _telemetry_root(),
            telemetry.firestore_in_service_checker(firestore.client()),
            iterations=4, interval_s=15)
