"""Borra del disco los archivos que ya nadie usa.

Django no toca el archivo cuando se elimina un registro o se reemplaza el
audio, la portada o el avatar: sin esto `media/` crece con cada cambio.

- Antes de guardar se anota qué archivos tenía el registro (pre_save).
- Después de guardar, si alguno cambió, el viejo se borra al confirmar la
  transacción (post_save + on_commit). Si el guardado falla, no se borra nada.
- Un guardado que no toca archivos (por ejemplo, last_login al entrar) no
  hace ninguna consulta extra.
"""

from django.db import transaction
from django.db.models import FileField
from django.db.models.signals import post_delete, post_save, pre_save


def _campos_archivo(modelo):
    return [campo for campo in modelo._meta.get_fields() if isinstance(campo, FileField)]


def _borrar_despues(storage, nombre):
    transaction.on_commit(lambda: storage.exists(nombre) and storage.delete(nombre))


def al_borrar(sender, instance, **kwargs):
    for campo in _campos_archivo(sender):
        archivo = getattr(instance, campo.name)
        if archivo and archivo.name:
            _borrar_despues(archivo.storage, archivo.name)


def antes_de_guardar(sender, instance, raw=False, update_fields=None, **kwargs):
    instance._kl_archivos_previos = {}
    if not instance.pk or raw:
        return
    campos = [c.name for c in _campos_archivo(sender)]
    if update_fields is not None:
        campos = [c for c in campos if c in update_fields]
    if not campos:
        return
    anterior = sender._default_manager.filter(pk=instance.pk).values(*campos).first()
    if anterior:
        instance._kl_archivos_previos = {c: v for c, v in anterior.items() if v}


def despues_de_guardar(sender, instance, **kwargs):
    previos = getattr(instance, "_kl_archivos_previos", None) or {}
    for nombre_campo, nombre_viejo in previos.items():
        actual = getattr(instance, nombre_campo)
        if nombre_viejo != getattr(actual, "name", None):
            _borrar_despues(actual.storage, nombre_viejo)
    instance._kl_archivos_previos = {}


def conectar(*modelos):
    for modelo in modelos:
        post_delete.connect(al_borrar, sender=modelo, dispatch_uid=f"kl-borrar-{modelo.__name__}")
        pre_save.connect(antes_de_guardar, sender=modelo, dispatch_uid=f"kl-reemplazar-{modelo.__name__}")
        post_save.connect(despues_de_guardar, sender=modelo, dispatch_uid=f"kl-reemplazado-{modelo.__name__}")
