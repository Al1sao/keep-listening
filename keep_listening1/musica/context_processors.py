"""Datos disponibles en todos los templates.

Corre en cada página: cada consulta acá la paga toda la navegación, así que se
piden solo los campos que hacen falta.
"""

from django.conf import settings

from .models import Cancion, Favorito, MeGusta
from .seleccion import ESCENAS

# Las escenas de la selección (hip hop, pop): el menú lleva a Explorar.
ESCENAS_NAV = [{"slug": slug, "nombre": datos["nombre"]} for slug, datos in ESCENAS.items()]
LOMOS_DEL_ESTANTE = 14


def navegacion(request):
    contexto = {
        "escenas_nav": ESCENAS_NAV,
        "canciones_pendientes_nav": 0,
        "favoritos_ids": set(),
        "me_gusta_ids": [],
        "estante": [],
        # Permite mostrar ayudas de desarrollo (por ejemplo, las cuentas de
        # prueba del login) sin que lleguen nunca a produccion.
        "debug": settings.DEBUG,
    }
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return contexto

    # Ids de canciones guardadas: permite pintar el corazon en cualquier listado
    # (un set: cada tarjeta pregunta "¿está?").
    contexto["favoritos_ids"] = set(
        Favorito.objects.filter(usuario=usuario).values_list("cancion_id", flat=True)
    )
    # Temas de Apple con me gusta: el corazón del reproductor los pinta llenos
    # (solo los ids), y los últimos 14 son los lomos del estante del menú lateral.
    me_gusta = MeGusta.objects.filter(usuario=usuario)
    contexto["me_gusta_ids"] = list(me_gusta.values_list("pista_id", flat=True))
    contexto["estante"] = [m.como_pista() for m in me_gusta[:LOMOS_DEL_ESTANTE]]
    if usuario.es_admin:
        contexto["canciones_pendientes_nav"] = Cancion.objects.pendientes().count()
    return contexto
