# RevKit: A Toolkit for Reversible Circuit Design (www.revkit.org)
# Copyright (C) 2009-2011  The RevKit Developers <revkit@informatik.uni-bremen.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os

from revkit import *

from PyQt4 import QtCore, QtGui

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class CircuitLineItem( QGraphicsItemGroup ):
    def __init__( self, index, width, parent = None ):
        QGraphicsItemGroup.__init__( self, parent )

        # Tool Tip
        self.setToolTip( "<b><font color=\"#606060\">Line:</font></b> %d" % index )

        # Create sub-lines
        x = 0
        for i in range( 0, width + 1 ):
            e_width = 15 if i == 0 or i == width else 30
            self.addToGroup( QGraphicsLineItem( x, index * 30, x + e_width, index * 30 ) )
            x += e_width

    def apply_simulation_results( self, results ):
        map( lambda e, v: e.setPen( QPen( Qt.darkGreen if v else Qt.red, 2 ) ), self.childItems(), results )

    def clear_simulation_results( self ):
        for item in self.childItems(): item.setPen( QPen( Qt.black, 0 ) )

class GateItem( QGraphicsItemGroup ):
    def __init__( self, g, index, circ, parent = None ):
        QGraphicsItemGroup.__init__( self, parent )
        self.setFlag( QGraphicsItem.ItemIsSelectable )

        l = control_lines( g )
        l.extend( target_lines( g ) )
        l.sort()

        self.gate = g
        annotations = [[ "Index", index ]] + circ.annotations( g ).items()
        self.setToolTip( '\n'.join( [ "<b><font color=\"#606060\">%s:</font></b> %s" % ( k, v ) for (k,v) in annotations ] ) )

        if len( l ) > 1:
            circuitLine = QGraphicsLineItem( 0, l[0] * 30, 0, l[-1] * 30, self )
            self.addToGroup( circuitLine )

        for t in target_lines( g ):
            if g.type == gate_type.toffoli:
                target = QGraphicsEllipseItem( -10, t * 30 - 10, 20, 20, self )
                targetLine = QGraphicsLineItem( 0, t * 30 - 10, 0, t * 30 + 10, self )
                targetLine2 = QGraphicsLineItem( -10, t * 30, 10, t * 30, self )
                self.addToGroup( target )
                self.addToGroup( targetLine )
                self.addToGroup( targetLine2 )
            if g.type == gate_type.fredkin:
                crossTL_BR = QGraphicsLineItem( -5, t * 30 - 5, 5, t * 30 + 5, self )
                crossTR_BL = QGraphicsLineItem( 5, t * 30 - 5, -5, t * 30 + 5, self )
                self.addToGroup( crossTL_BR )
                self.addToGroup( crossTR_BL )
            if g.type == gate_type.v:
                target = QGraphicsRectItem( -10, t * 30 - 10, 20, 20, self )
                target.setBrush( Qt.white )
                text = QGraphicsSimpleTextItem( "V", self )
                text.setPos( -4, t * 30 - 7 )
            if g.type == gate_type.vplus:
                target = QGraphicsRectItem( -10, t * 30 - 10, 20, 20, self )
                target.setBrush( Qt.white )
                text = QGraphicsSimpleTextItem( "V+", self )
                text.setPos( -4, t * 30 - 7 )

        if g.type == gate_type.module:
            min_target = min( target_lines( g ) )
            max_target = max( target_lines( g ) )
            box = QGraphicsRectItem( -10, min_target * 30 - 5, 20, ( max_target - min_target ) * 30 + 10, self )
            box.setBrush( Qt.white )

            for t in range( min_target + 1, max_target ):
                if t not in target_lines( g ):
                    line = QGraphicsLineItem( -10, t * 30, 10, t * 30, self )

            text = QGraphicsSimpleTextItem( g.module_name, self )
            width = QFontMetrics( text.font() ).width( g.module_name )
            height = QFontMetrics( text.font() ).height()
            text.setPos( -width / 2, ( min_target + max_target ) / 2 * 30 + height / 2 )
            text.setRotation( 270 )
            text.setTransformOriginPoint( width / 2, height / 2 )

            self.addToGroup( box )

        for c in control_lines( g ):
            control = QGraphicsEllipseItem( -5, c * 30 - 5, 10, 10, self )
            control.setBrush( Qt.black )
            self.addToGroup( control )

    def itemChange( self, change, value ):
        if change == QGraphicsItem.ItemSelectedChange:
            color = Qt.red if value.toBool() else Qt.black

            for item in filter( lambda x: type( x ) != QGraphicsSimpleTextItem, self.childItems() ):
                item.setPen( QPen( color ) )

            for item in filter( lambda x: x.brush().style() != Qt.NoBrush and x.brush().color() != Qt.white, filter( lambda x: issubclass( type( x ), QAbstractGraphicsShapeItem ), self.childItems() ) ):
                item.setBrush( color )
        return QGraphicsItemGroup.itemChange( self, change, value )

    def mouseDoubleClickEvent( self, event ):
        for v in self.scene().views():
            v.gateDoubleClicked.emit( self.gate )
        return QGraphicsItemGroup.mouseDoubleClickEvent( self, event )

class CircuitView( QGraphicsView ):
    gateDoubleClicked = pyqtSignal( gate )

    def __init__( self, circ = None, parent = None ):
        QGraphicsView.__init__( self, parent )

        self.setupActions()

        # Scene
        self.setScene( QGraphicsScene( self ) )
        self.scene().setBackgroundBrush( Qt.white )

        # Contextmenu
        self.setContextMenuPolicy( Qt.CustomContextMenu )
        self.connect( self, SIGNAL( 'customContextMenuRequested(const QPoint&)' ), self.contextMenu )

        # Load circuit
        self.circ = None
        if circ is not None:
            self.load( circ )

    def setupActions( self ):
        path = os.path.realpath( os.path.abspath( __file__ ) )
        path = path.replace( os.path.basename( __file__ ), '../tools/icons/' ) # TODO

        self.latexToClipboardAction = QAction( QIcon( path + 'text-x-tex.png' ), '&LaTeX to Clipboard', self )

        self.connect( self.latexToClipboardAction, SIGNAL( 'triggered()' ), self.latexToClipboard )

    def load( self, circ ):
        for item in self.scene().items():
            self.scene().removeItem( item )

        self.circ = circ
        self.lines = []
        self.inputs = []
        self.outputs = []

        width = 30 * circ.num_gates

        for i in range(0, circ.lines):
            line = CircuitLineItem( i, circ.num_gates )
            self.lines.append( line )
            self.scene().addItem( line )
            self.inputs.append( self.addLineLabel( 0, i * 30, circ.inputs[i], Qt.AlignRight, circ.constants[i] != None ) )
            self.outputs.append( self.addLineLabel( width, i * 30, circ.outputs[i], Qt.AlignLeft, circ.garbage[i] ) )

        index = 0
        for g in circ.gates:
            gateItem = GateItem( g, index, self.circ )
            gateItem.setPos( index * 30 + 15, 0 )
            self.scene().addItem( gateItem )
            index += 1

        # buses
        linestoadd = [] # strange bug, have to pre-save items to add
        toadd = [] # strange bug, have to pre-save items to add
        if not circ.inputbuses().empty():
            # largest label width
            offset = max( map( lambda l: l.boundingRect().width(), self.inputs ) )
            boundingRects = map( lambda l: l.boundingRect(), self.inputs )

            for bus in circ.inputbuses():
                # corresponding labels
                labels = map( lambda index: self.inputs[index], circ.inputbuses()[bus] )
                pos = map( lambda l: l.pos(), labels )
                rects = map( lambda index: boundingRects[index], circ.inputbuses()[bus] )

                # middle
                mid = ( min( map( lambda x: x.y(), pos ) ) + max( map( lambda p: p[0].y() + p[1].height(), zip( pos, rects ) ) ) ) / 2

                for p, r in zip( pos, rects ):
                    #path = QPainterPath()
                    #path.moveTo( -offset - 20, mid )
                    #path.quadTo( -offset - 10, p.y() + r.height() / 2,  p.x(), p.y() + r.height() / 2 )
                    #self.scene().addPath( path )
                    self.scene().addLine( -offset - 20, mid, p.x(), p.y() + r.height() / 2 )

                linestoadd.append( [ -offset - 40, mid, -offset - 20, mid ] )
                toadd.append( [ -offset - 40, mid, bus ] )

        for a in toadd:
            self.addLineLabel( a[0], a[1], a[2], Qt.AlignRight, False )
        for l in linestoadd:
            self.scene().addLine( l[0], l[1], l[2], l[3], QPen( Qt.black, 1.5 ) )

        toadd = []
        linestoadd = []
        if not circ.outputbuses().empty():
            # largest label width
            offset = max( map( lambda l: l.boundingRect().width(), self.outputs ) )
            boundingRects = map( lambda l: l.boundingRect(), self.outputs )

            for bus in circ.outputbuses():
                # corresponding labels
                labels = map( lambda index: self.outputs[index], circ.outputbuses()[bus] )
                pos = map( lambda l: l.pos(), labels )
                rects = map( lambda index: boundingRects[index], circ.outputbuses()[bus] )

                # middle
                mid = ( min( map( lambda x: x.y(), pos ) ) + max( map( lambda p: p[0].y() + p[1].height(), zip( pos, rects ) ) ) ) / 2

                for p, r in zip( pos, rects ):
                    self.scene().addLine( width + offset + 20, mid, p.x() + r.width(), p.y() + r.height() / 2 )

                linestoadd.append( [ width + offset + 20, mid, width + offset + 40, mid ] )
                toadd.append( [ width + offset + 40, mid, bus ] )

        for a in toadd:
            self.addLineLabel( a[0], a[1], a[2], Qt.AlignLeft, False )
        for l in linestoadd:
            self.scene().addLine( l[0], l[1], l[2], l[3], QPen( Qt.black, 1.5 ) )

        # State Signals
        # toadd = [] # strange bug, have to pre-save items to add
        # if not circ.statesignals().empty():
        #     # largest label width
        #     offset = max( map( lambda l: l.boundingRect().width(), self.inputs ) )
        #     boundingRects = map( lambda l: l.boundingRect(), self.inputs )

        #     offset_o = max( map( lambda l: l.boundingRect().width(), self.outputs ) )
        #     boundingRects_o = map( lambda l: l.boundingRect(), self.outputs )

        #     for bus in circ.statesignals():
        #         # corresponding labels
        #         labels = map( lambda index: self.inputs[index], circ.statesignals()[bus] )
        #         labels_o = map( lambda index: self.outputs[index], circ.statesignals()[bus] )
        #         pos = map( lambda l: l.pos(), labels )
        #         pos_o = map( lambda l: l.pos(), labels_o )
        #         rects = map( lambda index: boundingRects[index], circ.statesignals()[bus] )
        #         rects_o = map( lambda index: boundingRects_o[index], circ.statesignals()[bus] )

        #         # middle
        #         mid = ( min( map( lambda x: x.y(), pos ) ) + max( map( lambda p: p[0].y() + p[1].height(), zip( pos, rects ) ) ) ) / 2

        #         for p, r in zip( pos, rects ):
        #             self.scene().addLine( -offset - 20, mid, p.x(), p.y() + r.height() / 2 )

        #         for p, r in zip( pos_o, rects_o ):
        #             self.scene().addLine( width + offset_o + 20, mid, p.x() + r.width(), p.y() + r.height() / 2 )

        #         self.scene().addLine( -offset - 40, mid, -offset - 20, mid, QPen( Qt.black, 1.5 ) )

        #         self.scene().addLine( width + offset_o + 20, mid, width + offset_o + 40, mid, QPen( Qt.black, 1.5 ) )

    def addLineLabel(self, x, y, text, align, color):
        textItem = self.scene().addText( text )
        textItem.setPlainText( text )

        if align == Qt.AlignRight:
            x -= textItem.boundingRect().width()

        textItem.setPos( x, y - 12 )

        if color:
            textItem.setDefaultTextColor( Qt.red )

        return textItem

    def simulate( self, inp ):
        if len( inp ) != self.circ.lines:
            return

        line_values = dict()
        for i in range( 0, len( inp ) ):
            line_values[i] = [not not inp[i]]

        def step_result_f( g, result ):
            for i in range( 0, len( result ) ):
                line_values[i].append( result[i] )

        output = []
        simple_simulation( output, self.circ, inp, step_result = step_result_f )

        # Display results
        for i in range( 0, len( inp ) ):
            self.inputs[i].setPlainText( self.circ.inputs[i] + " = " + str( int( line_values[i][0] ) ) )
            self.inputs[i].setPos( -self.inputs[i].boundingRect().width(), self.inputs[i].y() )
            self.outputs[i].setPlainText( self.circ.outputs[i] + " = " + str( int( line_values[i][-1] ) ) )
            self.lines[i].apply_simulation_results( line_values[i] )

    def clear_simulation( self ):
        for i in range( 0, self.circ.lines ):
            self.inputs[i].setPlainText( self.circ.inputs[i] )
            self.inputs[i].setPos( -self.inputs[i].boundingRect().width(), self.inputs[i].y() )
            self.outputs[i].setPlainText( self.circ.outputs[i] )
            self.lines[i].clear_simulation_results()

    def wheelEvent( self, event ):
        factor = 1.2
        if event.delta() < 0:
            factor = 1.0 / factor
        self.scale( factor, factor )
        self.updateZoomValue()
        return QGraphicsView.wheelEvent( self, event )

    # Zoom Widget
    zoom_widget = None
    def zoomWidget( self ):
        if self.zoom_widget is None:
            path = os.path.realpath( os.path.abspath( __file__ ) )
            path = path.replace( os.path.basename( __file__ ), '../tools/icons/' ) # TODO

            self.zoom_widget = QWidget( self )

            # Components
            zoomActualSize = QToolButton( self.zoom_widget )
            zoomActualSize.setIcon( QIcon( path + "zoom-original.png" ) )
            zoomActualSize.setToolTip( "Zoom to original size" )
            zoomActualSize.setAutoRaise( True )
            zoomOut = QToolButton( self.zoom_widget )
            zoomOut.setIcon( QIcon( path + "zoom-out.png" ) )
            zoomOut.setToolTip( "Zoom out" )
            zoomOut.setAutoRaise( True )
            zoomIn = QToolButton( self.zoom_widget )
            zoomIn.setIcon( QIcon( path + "zoom-in.png" ) )
            zoomIn.setToolTip( "Zoom in" )
            zoomIn.setAutoRaise( True )
            zoomSlider = QSlider( Qt.Horizontal, self.zoom_widget )
            zoomSlider.setMinimum( 25 )
            zoomSlider.setMaximum( 1600 )
            zoomSlider.setValue( 100 )

            self.connect( zoomActualSize, SIGNAL( 'clicked()' ), lambda: zoomSlider.setValue( 100 ) )
            self.connect( zoomOut, SIGNAL( 'clicked()' ), self.zoomOutClicked )
            self.connect( zoomIn, SIGNAL( 'clicked()' ), self.zoomInClicked )
            self.connect( zoomSlider, SIGNAL( 'valueChanged(int)' ), self.zoomSliderValueChanged )

            layout = QHBoxLayout()
            layout.setMargin( 0 )
            layout.setSpacing( 0 )
            layout.addWidget( zoomActualSize )
            layout.addWidget( zoomOut )
            layout.addWidget( zoomSlider )
            layout.addWidget( zoomIn )
            self.zoom_widget.setLayout( layout )
            self.zoom_widget.setMaximumWidth( 180 )

        self.updateZoomValue()
        return self.zoom_widget

    def updateZoomValue( self ):
        if self.zoom_widget is not None:
            slider = [ w for w in self.zoom_widget.children() if isinstance( w, QSlider ) ][0]
            slider.setValue( self.transform().m11() * 100 )

    def zoomOutClicked( self ):
        slider = [ w for w in self.zoom_widget.children() if isinstance( w, QSlider ) ][0]
        v = slider.value()
        if v > 100:
            delta = v % 100
            if delta == 0:
                delta = 100
            slider.setValue( v - delta )
        else:
            delta = v % 25
            if delta == 0:
                delta = 25
            slider.setValue( v - delta )

    def zoomInClicked( self ):
        slider = [ w for w in self.zoom_widget.children() if isinstance( w, QSlider ) ][0]
        v = slider.value()
        if v >= 100:
            delta = 100 - ( v % 100 )
            slider.setValue( v + delta )
        else:
            delta = 25 - ( v % 25 )
            slider.setValue( v + delta )

    def zoomSliderValueChanged( self, value ):
        transform = QTransform()
        transform.scale( value / 100.0, value / 100.0 )
        self.setTransform( transform )
        QToolTip.showText( self.sender().mapToGlobal( QPoint( 0, 0 ) ), "%d%%" % value )

    # Slots
    def latexToClipboard( self ):
        if self.circ is not None:
            QApplication.clipboard().setText( create_image( self.circ ) )

    def contextMenu( self, pos ):
        menu = QMenu( self )
        menu.addAction( self.latexToClipboardAction )
        menu.popup( self.mapToGlobal( pos ) )

# HierarchyModel
class HierarchyModel( QAbstractItemModel ):
    def __init__( self, tree ):
        QAbstractItemModel.__init__( self )
        self.tree = tree

    def columnCount( self, parent ):
        return 2

    def headerData( self, section, orientation, role ):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return [ "Module", "Lines" ][section]
        return QVariant()

    def rowCount( self, parent ):
        if ( parent.column() > 0 ):
            return 0

        if not parent.isValid():
            return 1
        else:
            return len( self.tree.children( parent.internalId() ) )

    def data( self, index, role ):
        if not index.isValid():
            return QVariant()

        if role == Qt.DisplayRole:
            if index.column() == 0:
                return self.tree.node_name( index.internalId() )
            else:
                return str( self.tree.node_circuit( index.internalId() ).lines )

        if index.column() == 1 and role == Qt.TextAlignmentRole:
            return Qt.AlignRight

        return QVariant()

    def index( self, row, column, parent = QModelIndex() ):
        if not self.hasIndex( row, column, parent ):
            return QModelIndex()

        if not parent.isValid():
            return self.createIndex( row, column, self.tree.root() )
        else:
            return self.createIndex( row, column, self.tree.children( parent.internalId() )[row] )

    def parent( self, index ):
        if not index.isValid():
            return QModelIndex()

        childId = index.internalId()
        if childId == self.tree.root():
            return QModelIndex()
        else:
            parentId = self.tree.parent( childId )
            row = 0 if parentId == self.tree.root() else self.tree.children( self.tree.parent( parentId ) ).index( parentId )
            return self.createIndex( row, 0, parentId )

class LineNumberArea( QWidget ):
    def __init__( self, editor ):
        QWidget.__init__( self, editor )
        self.codeEditor = editor

    def sizeHint( self ):
        return QSize( self.codeEditor.lineNumberAreaWidth(), 0 )

    def paintEvent( self, event ):
        self.codeEditor.lineNumberAreaPaintEvent( event )

class CodeEditor( QPlainTextEdit ):
    def __init__( self, parent = None ):
        QPlainTextEdit.__init__( self, parent )

        self.lineNumberArea = LineNumberArea( self )

        self.connect( self, SIGNAL( 'blockCountChanged(int)' ), self.updateLineNumberAreaWidth )
        self.connect( self, SIGNAL( 'updateRequest(const QRect&, int)' ), self.updateLineNumberArea )
        self.connect( self, SIGNAL( 'cursorPositionChanged()' ), self.highlightCurrentLine )

        self.updateLineNumberAreaWidth( 0 )
        self.highlightCurrentLine()

    def load( self, filename ):
        if len( filename ) > 0:
            self.setPlainText( open( filename, 'r' ).read() )

    def lineNumberAreaPaintEvent( self, event ):
        painter = QPainter( self.lineNumberArea )
        painter.fillRect( event.rect(), Qt.lightGray )

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry( block ).translated( self.contentOffset() ).top()
        bottom = top + self.blockBoundingGeometry( block ).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = QString.number( blockNumber + 1 )
                painter.setPen( Qt.black )
                painter.drawText( 0, top, self.lineNumberArea.width(), self.fontMetrics().height(), Qt.AlignRight, number )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingGeometry( block ).height()
            blockNumber += 1

    def lineNumberAreaWidth( self ):
        digits = 1
        max_ = max( 1, self.blockCount() )
        while ( max_ >= 10 ):
            max_ /= 10
            digits += 1

        space = 3 + self.fontMetrics().width( '9' ) * digits
        return space

    def resizeEvent( self, event ):
        QPlainTextEdit.resizeEvent( self, event )

        cr = self.contentsRect()
        self.lineNumberArea.setGeometry( QRect( cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height() ) )

    def updateLineNumberAreaWidth( self, newBlockCount ):
        self.setViewportMargins( self.lineNumberAreaWidth(), 0, 0, 0 )

    def highlightCurrentLine( self ):
        extraSelections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            lineColor = QColor( Qt.yellow ).lighter( 160 )

            selection.format.setBackground( lineColor )
            selection.format.setProperty( QTextFormat.FullWidthSelection, True )
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append( selection )

        self.setExtraSelections( extraSelections )

    def updateLineNumberArea( self, rect, dy ):
        if dy != 0:
            self.lineNumberArea.scroll( 0, dy )
        else:
            self.lineNumberArea.update( 0, rect.y(), self.lineNumberArea.width(), rect.height() )

        if rect.contains( self.viewport().rect() ):
            self.updateLineNumberAreaWidth( 0 )

class RevLibHighlighter( QSyntaxHighlighter ):
    def __init__( self, parent ):
        QSyntaxHighlighter.__init__( self, parent )

        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground( Qt.darkRed )
        keywords = [ "version", "numvars", "variables", "inputs", "outputs", "inputbus", "outputbus", "state", "constants", "garbage", "module", "begin", "end" ]

        for pattern in [ "\\.%s" % keyword for keyword in keywords ]:
            self.highlightingRules.append( [ QRegExp( pattern ), keywordFormat ] )

        gateFormat = QTextCharFormat()
        gateFormat.setForeground( Qt.darkBlue )
        gateFormat.setFontWeight( QFont.Bold )
        gates = [ "t", "f", "p", "v" ]

        for pattern in [ "\\b%s\\d*\\b" % gate for gate in gates ]:
            self.highlightingRules.append( [ QRegExp( pattern ), gateFormat ] )
        self.highlightingRules.append( [ QRegExp( "v\\+" ), gateFormat ] )

        numberFormat = QTextCharFormat()
        numberFormat.setForeground( Qt.darkCyan )
        self.highlightingRules.append( [ QRegExp( "\\b[0-9]+\\b" ), numberFormat ] )

        commentFormat = QTextCharFormat()
        commentFormat.setForeground( Qt.darkGray )
        commentFormat.setFontItalic( True )
        self.highlightingRules.append( [ QRegExp( "#.*$" ), commentFormat ] )

    def highlightBlock( self, text ):
        for rule in self.highlightingRules:
            expression = rule[0]
            index = expression.indexIn( text )
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat( index, length, rule[1] )
                index = expression.indexIn( text, index + length )

class RevLibEditor( CodeEditor ):
    def __init__( self, parent = None ):
        CodeEditor.__init__( self, parent )

        self.highlighter = RevLibHighlighter( self.document() )
        self.setFont( QFont( "Monospace" ) )

