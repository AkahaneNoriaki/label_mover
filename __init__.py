# __init__.py
# QGISはこのファイルを見てプラグインを認識します。
# classFactory関数は必ず必要です。

def classFactory(iface):
    """
    QGISがプラグインを読み込むときに最初に呼ばれる関数。
    iface: QGISのメイン画面へのアクセス手段（QgisInterface）
    """
    from .label_mover import LabelMoverPlugin
    return LabelMoverPlugin(iface)
