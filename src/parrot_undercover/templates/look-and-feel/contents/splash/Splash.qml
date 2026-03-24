import QtQuick
import org.kde.kirigami 2 as Kirigami

Rectangle {
    id: root
    color: "__SPLASH_BACKGROUND__"

    property int stage

    Item {
        id: content
        anchors.fill: parent

        Image {
            id: logo
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -Kirigami.Units.gridUnit * 2
            asynchronous: true
            fillMode: Image.PreserveAspectFit
            source: "__START_ICON_URI__"
            sourceSize.width: Kirigami.Units.gridUnit * 6
            sourceSize.height: Kirigami.Units.gridUnit * 6
            width: Kirigami.Units.gridUnit * 6
            height: Kirigami.Units.gridUnit * 6
        }

        Item {
            id: spinner
            width: Kirigami.Units.gridUnit * 4
            height: Kirigami.Units.gridUnit * 4
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: logo.bottom
            anchors.topMargin: Kirigami.Units.gridUnit * 1.5

            Repeater {
                model: 6

                delegate: Rectangle {
                    required property int index

                    width: Kirigami.Units.smallSpacing + 2
                    height: width
                    radius: width / 2
                    color: "#ffffff"
                    opacity: 0.25 + (index * 0.1)

                    readonly property real angle: (index / 6) * Math.PI * 2
                    readonly property real ringRadius: spinner.width * 0.28

                    x: spinner.width / 2 + Math.cos(angle) * ringRadius - width / 2
                    y: spinner.height / 2 + Math.sin(angle) * ringRadius - height / 2
                }
            }

            RotationAnimator on rotation {
                from: 0
                to: 360
                duration: 1100
                loops: Animation.Infinite
                running: true
            }
        }
    }
}
