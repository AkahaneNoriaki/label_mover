# label_mover_fixed.py
# プラグインのメインコードです。

from qgis.PyQt.QtWidgets import (
    QAction, QMessageBox, QColorDialog,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QPushButton, QDialogButtonBox,
    QCheckBox, QGroupBox
)
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProject,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsUnitTypes,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsVectorLayer,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsTextBufferSettings,
    QgsFeatureRequest,
)


class TextStyleDialog(QDialog):
    """
    テキストスタイル設定ダイアログ。
    フォントサイズ・色・太字・斜体・バッファーを設定できます。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("テキストスタイルを一括設定")
        self.setMinimumWidth(320)

        self._font_color = QColor(0, 0, 0)
        self._buffer_color = QColor(255, 255, 255)

        layout = QVBoxLayout()

        font_group = QGroupBox("フォント設定")
        font_layout = QVBoxLayout()

        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("フォントサイズ（pt）："))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(4, 72)
        self.spin_size.setValue(9)
        size_layout.addWidget(self.spin_size)
        font_layout.addLayout(size_layout)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("フォント色："))
        self.btn_font_color = QPushButton("　　　　")
        self.btn_font_color.setStyleSheet("background-color: black;")
        self.btn_font_color.clicked.connect(self._pick_font_color)
        color_layout.addWidget(self.btn_font_color)
        font_layout.addLayout(color_layout)

        style_layout = QHBoxLayout()
        self.chk_bold = QCheckBox("太字")
        self.chk_italic = QCheckBox("斜体")
        style_layout.addWidget(self.chk_bold)
        style_layout.addWidget(self.chk_italic)
        font_layout.addLayout(style_layout)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        buffer_group = QGroupBox("バッファー（ハロー）設定")
        buffer_layout = QVBoxLayout()

        self.chk_buffer = QCheckBox("バッファーを有効にする")
        self.chk_buffer.setChecked(True)
        buffer_layout.addWidget(self.chk_buffer)

        buf_size_layout = QHBoxLayout()
        buf_size_layout.addWidget(QLabel("バッファーサイズ（mm）："))
        self.spin_buffer_size = QDoubleSpinBox()
        self.spin_buffer_size.setRange(0.1, 10.0)
        self.spin_buffer_size.setSingleStep(0.1)
        self.spin_buffer_size.setValue(0.5)
        buf_size_layout.addWidget(self.spin_buffer_size)
        buffer_layout.addLayout(buf_size_layout)

        buf_color_layout = QHBoxLayout()
        buf_color_layout.addWidget(QLabel("バッファー色："))
        self.btn_buffer_color = QPushButton("　　　　")
        self.btn_buffer_color.setStyleSheet("background-color: white; border: 1px solid gray;")
        self.btn_buffer_color.clicked.connect(self._pick_buffer_color)
        buf_color_layout.addWidget(self.btn_buffer_color)
        buffer_layout.addLayout(buf_color_layout)

        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _pick_font_color(self):
        color = QColorDialog.getColor(self._font_color, self, "フォント色を選択")
        if color.isValid():
            self._font_color = color
            self.btn_font_color.setStyleSheet(f"background-color: {color.name()};")

    def _pick_buffer_color(self):
        color = QColorDialog.getColor(self._buffer_color, self, "バッファー色を選択")
        if color.isValid():
            self._buffer_color = color
            self.btn_buffer_color.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid gray;"
            )

    def get_settings(self):
        return {
            "font_size": self.spin_size.value(),
            "font_color": self._font_color,
            "bold": self.chk_bold.isChecked(),
            "italic": self.chk_italic.isChecked(),
            "buffer_enabled": self.chk_buffer.isChecked(),
            "buffer_size": self.spin_buffer_size.value(),
            "buffer_color": self._buffer_color,
        }


class LabelMoverPlugin:
    """
    プラグインのメインクラス。
    """

    def __init__(self, iface):
        self.iface = iface
        self._layout_toolbars = {}
        self._current_index = {}
        self._active_designer = None  # 現在開いているレイアウトデザイナーを保持

    def initGui(self):
        self.action_all = QAction("印刷範囲内のラベルを一括追加", self.iface.mainWindow())
        self.action_all.setToolTip(
            "アクティブレイヤーの印刷範囲内フィーチャのラベルをレイアウトに追加します"
        )
        self.action_all.triggered.connect(self.run_all)
        self.iface.addPluginToMenu("Label Mover", self.action_all)

        self.action_style = QAction("テキストスタイルを一括設定", self.iface.mainWindow())
        self.action_style.setToolTip(
            "フォントサイズ・色・太字・斜体・バッファーを全テキストアイテムに一括適用します"
        )
        self.action_style.triggered.connect(self.run_style)
        self.iface.addPluginToMenu("Label Mover", self.action_style)

        self.action_clear = QAction("クリア（テキスト削除＋ラベル再表示）", self.iface.mainWindow())
        self.action_clear.setToolTip(
            "レイアウトに追加したテキストアイテムを全て削除し、元のラベルを再表示します"
        )
        self.action_clear.triggered.connect(self.run_clear)
        self.iface.addPluginToMenu("Label Mover", self.action_clear)

        self.action_restore = QAction("元のラベルを再表示", self.iface.mainWindow())
        self.action_restore.setToolTip("非表示にした元のラベルをもとに戻します")
        self.action_restore.triggered.connect(self.run_restore)
        self.iface.addPluginToMenu("Label Mover", self.action_restore)

        try:
            self.iface.layoutDesignerOpened.disconnect(self._on_layout_opened)
        except Exception:
            pass
        self.iface.layoutDesignerOpened.connect(self._on_layout_opened)

    def unload(self):
        self.iface.removePluginMenu("Label Mover", self.action_all)
        self.iface.removePluginMenu("Label Mover", self.action_style)
        self.iface.removePluginMenu("Label Mover", self.action_clear)
        self.iface.removePluginMenu("Label Mover", self.action_restore)

        try:
            self.iface.layoutDesignerOpened.disconnect(self._on_layout_opened)
        except Exception:
            pass

        for toolbar in self._layout_toolbars.values():
            try:
                toolbar.deleteLater()
            except Exception:
                pass
        self._layout_toolbars.clear()
        self._current_index.clear()

    def _on_layout_opened(self, layout_designer):
        from qgis.PyQt.QtWidgets import QToolBar

        # 現在開いているデザイナーを保持
        self._active_designer = layout_designer

        layout = layout_designer.layout()
        try:
            layout_name = layout.name()
        except AttributeError:
            layout_name = str(id(layout))

        main_win = layout_designer.window()
        if main_win is None:
            return

        # 既存のツールバーがあれば削除
        old_toolbar = self._layout_toolbars.get(layout_name)
        if old_toolbar is not None:
            try:
                main_win.removeToolBar(old_toolbar)
                old_toolbar.deleteLater()
            except Exception:
                pass

        # ツールバーを作成して全ボタンを追加
        toolbar = QToolBar("Label Mover", main_win)

        # ① 一括追加ボタン
        action_all = QAction("ラベル追加", main_win)
        action_all.setToolTip("印刷範囲内のラベルを一括追加します")
        action_all.triggered.connect(self.run_all)
        toolbar.addAction(action_all)

        # ② スタイル設定ボタン
        action_style = QAction("スタイル設定", main_win)
        action_style.setToolTip("フォント・色・バッファーを一括設定します")
        action_style.triggered.connect(self.run_style)
        toolbar.addAction(action_style)

        toolbar.addSeparator()

        # ③ 次のラベルへボタン
        action_next = QAction("▶ 次のラベルへ", main_win)
        action_next.setToolTip("次のテキストアイテムを選択します（順番に移動）")
        action_next.triggered.connect(lambda: self._select_next_label(layout))
        toolbar.addAction(action_next)

        toolbar.addSeparator()

        # ④ クリアボタン
        action_clear = QAction("クリア", main_win)
        action_clear.setToolTip("テキストアイテムを全削除し、元のラベルを再表示します")
        action_clear.triggered.connect(self.run_clear)
        toolbar.addAction(action_clear)

        # ⑤ 元のラベルを再表示ボタン
        action_restore = QAction("ラベル再表示", main_win)
        action_restore.setToolTip("非表示にした元のラベルをもとに戻します")
        action_restore.triggered.connect(self.run_restore)
        toolbar.addAction(action_restore)

        toolbar.addSeparator()

        # ⑥ 重なりアラートボタン
        action_overlap = QAction("⚠ 重なり確認", main_win)
        action_overlap.setToolTip("重なっているテキストアイテムを赤色でハイライトします")
        action_overlap.triggered.connect(lambda: self.run_overlap_check(layout))
        toolbar.addAction(action_overlap)

        main_win.addToolBar(toolbar)
        self._layout_toolbars[layout_name] = toolbar
        self._current_index[layout_name] = -1

    def _select_next_label(self, layout):
        label_items = [item for item in layout.items() if isinstance(item, QgsLayoutItemLabel)]
        if not label_items:
            return

        try:
            layout_name = layout.name()
        except AttributeError:
            layout_name = str(id(layout))

        current = self._current_index.get(layout_name, -1)
        next_index = (current + 1) % len(label_items)
        self._current_index[layout_name] = next_index

        layout.deselectAll()
        label_items[next_index].setSelected(True)

    def run_all(self):
        layer = self.iface.activeLayer()
        if layer is None:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "レイヤーが選択されていません。")
            return

        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "ベクターレイヤーを選択してください。")
            return

        label_expr = self._get_label_expression(layer)
        if label_expr is None:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "このレイヤーにはラベル設定がありません。")
            return

        layout = self._get_active_layout()
        if layout is None:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "印刷レイアウトが見つかりません。")
            return

        map_item = self._get_map_item(layout)
        if map_item is None:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "レイアウト内に地図アイテムが見つかりません。")
            return

        print_extent = map_item.extent()
        project = QgsProject.instance()

        extent_in_layer_crs = self._transform_extent(print_extent, project.crs(), layer.crs())
        features_in_extent = layer.getFeatures(QgsFeatureRequest().setFilterRect(extent_in_layer_crs))

        total_added = 0
        for feature in features_in_extent:
            feature_point = self._get_feature_point(feature, layer)
            feature_point_prj = self._transform_point(feature_point, layer.crs(), project.crs())
            if not print_extent.contains(feature_point_prj):
                continue

            label_text = self._evaluate_label(feature, layer, label_expr)
            if not label_text:
                continue

            layout_pos = self._map_to_layout(feature_point, map_item, layer)
            self._add_label_to_layout(layout, label_text, layout_pos)
            total_added += 1

        self._set_label_visibility(layer, False)

        if total_added == 0:
            QMessageBox.information(
                self._get_parent_window(),
                "Label Mover",
                "印刷範囲内にラベル設定のあるフィーチャが見つかりませんでした。",
            )
        else:
            QMessageBox.information(
                self._get_parent_window(),
                "Label Mover",
                f"{total_added} 件のラベルをレイアウトに追加しました。\nレイアウト上でドラッグして位置を調整してください。",
            )

        self.iface.mapCanvas().refresh()

    def run_style(self):
        layout = self._get_active_layout()
        if layout is None:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "印刷レイアウトが見つかりません。")
            return

        label_items = [item for item in layout.items() if isinstance(item, QgsLayoutItemLabel)]
        if not label_items:
            QMessageBox.warning(self._get_parent_window(), "Label Mover", "レイアウト上にテキストアイテムがありません。")
            return

        dlg = TextStyleDialog(self._get_parent_window())
        if dlg.exec_() != QDialog.Accepted:
            return

        s = dlg.get_settings()

        for item in label_items:
            text_format = item.textFormat()
            font = text_format.font()
            font.setPointSize(s["font_size"])
            font.setBold(s["bold"])
            font.setItalic(s["italic"])
            text_format.setFont(font)
            text_format.setColor(s["font_color"])

            buffer_settings = QgsTextBufferSettings()
            buffer_settings.setEnabled(s["buffer_enabled"])
            buffer_settings.setSize(s["buffer_size"])
            buffer_settings.setSizeUnit(QgsUnitTypes.RenderMillimeters)
            buffer_settings.setColor(s["buffer_color"])
            text_format.setBuffer(buffer_settings)

            item.setTextFormat(text_format)
            item.setBackgroundEnabled(False)
            item.adjustSizeToText()
            item.refresh()

        QMessageBox.information(
            self._get_parent_window(),
            "Label Mover",
            f"{len(label_items)} 件のテキストアイテムにスタイルを適用しました。",
        )

    def run_clear(self):
        reply = QMessageBox.question(
            self._get_parent_window(),
            "Label Mover",
            "レイアウトのテキストアイテムを全て削除し、元のラベルを再表示します。\nよろしいですか？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        layout = self._get_active_layout()
        deleted = 0
        if layout is not None:
            items_to_delete = [item for item in layout.items() if isinstance(item, QgsLayoutItemLabel)]
            for item in items_to_delete:
                layout.removeLayoutItem(item)
                deleted += 1

        layer = self.iface.activeLayer()
        restored = 0
        if layer and isinstance(layer, QgsVectorLayer):
            if self._get_label_expression(layer) is not None:
                self._set_label_visibility(layer, True)
                restored += 1

        self.iface.mapCanvas().refresh()

        QMessageBox.information(
            self._get_parent_window(),
            "Label Mover",
            f"テキストアイテムを {deleted} 件削除し、\n{restored} 個のレイヤーのラベルを再表示しました。",
        )

    def run_restore(self):
        layer = self.iface.activeLayer()
        if layer and isinstance(layer, QgsVectorLayer):
            if self._get_label_expression(layer) is not None:
                self._set_label_visibility(layer, True)

        self.iface.mapCanvas().refresh()
        QMessageBox.information(self._get_parent_window(), "Label Mover", "元のラベルを再表示しました。")

    def run_overlap_check(self, layout):
        """
        レイアウト上のテキストアイテムの重なりを検出します。
        重なっているアイテムのフォントを赤くしてアラートします。
        """
        label_items = [
            item for item in layout.items()
            if isinstance(item, QgsLayoutItemLabel)
        ]
        if not label_items:
            QMessageBox.information(
                self._get_parent_window(), "Label Mover",
                "レイアウト上にテキストアイテムがありません。"
            )
            return

        # まず全アイテムのフォントを黒に戻す
        for item in label_items:
            text_format = item.textFormat()
            text_format.setColor(QColor(0, 0, 0))
            item.setTextFormat(text_format)
            item.refresh()

        # 重なりを検出して赤くハイライト
        overlap_count = 0
        for i, item_a in enumerate(label_items):
            rect_a = item_a.sceneBoundingRect()
            for item_b in label_items[i + 1:]:
                rect_b = item_b.sceneBoundingRect()
                if rect_a.intersects(rect_b):
                    # 両方のアイテムを赤にする
                    for item in (item_a, item_b):
                        text_format = item.textFormat()
                        text_format.setColor(QColor(255, 0, 0))
                        item.setTextFormat(text_format)
                        item.refresh()
                    overlap_count += 1

        if overlap_count == 0:
            QMessageBox.information(
                self._get_parent_window(), "Label Mover",
                "重なっているテキストアイテムはありません。"
            )
        else:
            QMessageBox.warning(
                self._get_parent_window(), "Label Mover",
                f"{overlap_count} 箇所の重なりが見つかりました。\n"
                "赤色のテキストアイテムを移動して調整してください。"
            )

    def _get_parent_window(self):
        """
        ポップアップの親ウィンドウを返します。
        レイアウトデザイナーが開いている場合はそちらを、
        そうでない場合はメインウィンドウを返します。
        """
        if self._active_designer is not None:
            try:
                win = self._active_designer.window()
                if win is not None:
                    return win
            except Exception:
                pass
        return self._get_parent_window()

    def _get_label_expression(self, layer):
        labeling = layer.labeling()
        if labeling is None:
            return None
        try:
            settings = labeling.settings()
            field_name = settings.fieldName
            if field_name:
                return field_name
        except Exception:
            pass
        return None

    def _evaluate_label(self, feature, layer, label_expr):
        fields = layer.fields()
        field_names = [f.name() for f in fields]

        if label_expr in field_names:
            val = feature[label_expr]
            if val is None:
                return None
            text = str(val).strip()
            if text == "" or text.upper() == "NULL":
                return None
            return text

        expr = QgsExpression(label_expr)
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        context.setFeature(feature)
        result = expr.evaluate(context)
        if result is None:
            return None

        text = str(result).strip()
        if text == "" or text.upper() == "NULL" or text == "None":
            return None

        import re
        text = re.sub(r"\bNULL\b", "", text, flags=re.IGNORECASE)
        text = text.strip(" 　\t\n")
        return text or None

    def _set_label_visibility(self, layer, visible):
        labeling = layer.labeling()
        if labeling is None:
            return
        try:
            settings = labeling.settings()
            settings.drawLabels = visible
            labeling.setSettings(settings)
            layer.setLabeling(labeling)
            layer.triggerRepaint()
        except Exception:
            pass

    def _get_active_layout(self):
        layouts = QgsProject.instance().layoutManager().printLayouts()
        return layouts[0] if layouts else None

    def _get_map_item(self, layout):
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                return item
        return None

    def _transform_extent(self, extent, src_crs, dst_crs):
        if src_crs == dst_crs:
            return extent
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
        return transform.transformBoundingBox(extent)

    def _transform_point(self, point, src_crs, dst_crs):
        if src_crs == dst_crs:
            return point
        transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
        return transform.transform(point)

    def _get_feature_point(self, feature, layer):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            return QgsPointXY(0, 0)

        try:
            pt = geom.pointOnSurface().asPoint()
            return QgsPointXY(pt)
        except Exception:
            pass

        centroid = geom.centroid()
        if centroid and not centroid.isEmpty():
            try:
                if centroid.isMultipart():
                    pts = centroid.asMultiPoint()
                    if pts:
                        return QgsPointXY(pts[0])
                return QgsPointXY(centroid.asPoint())
            except Exception:
                pass

        return QgsPointXY(geom.boundingBox().center())

    def _map_to_layout(self, map_point, map_item, layer):
        project_crs = QgsProject.instance().crs()
        layer_crs = layer.crs()

        if layer_crs != project_crs:
            transform = QgsCoordinateTransform(layer_crs, project_crs, QgsProject.instance())
            map_point = transform.transform(map_point)

        map_extent = map_item.extent()
        map_pos = map_item.pos()
        map_size = map_item.sizeWithUnits()

        map_x_min = map_extent.xMinimum()
        map_x_max = map_extent.xMaximum()
        map_y_min = map_extent.yMinimum()
        map_y_max = map_extent.yMaximum()

        dx = map_x_max - map_x_min
        dy = map_y_max - map_y_min
        if dx == 0 or dy == 0:
            return (map_pos.x(), map_pos.y())

        ratio_x = (map_point.x() - map_x_min) / dx
        ratio_y = (map_y_max - map_point.y()) / dy

        x_mm = map_pos.x() + ratio_x * map_size.width()
        y_mm = map_pos.y() + ratio_y * map_size.height()
        return (x_mm, y_mm)

    def _add_label_to_layout(self, layout, text, layout_pos):
        label_item = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(label_item)
        label_item.setText(text)
        label_item.setBackgroundEnabled(False)

        text_format = label_item.textFormat()
        text_format.setColor(QColor(0, 0, 0))
        label_item.setTextFormat(text_format)

        label_item.adjustSizeToText()
        x_mm, y_mm = layout_pos
        label_item.attemptMove(QgsLayoutPoint(x_mm + 2, y_mm - 5, QgsUnitTypes.LayoutMillimeters))
        label_item.refresh()
