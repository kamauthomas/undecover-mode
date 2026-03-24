var panel = new Panel
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.5 / 2);

var launcher = panel.addWidget("org.kde.plasma.kicker");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("useCustomButtonImage", "true");
launcher.writeConfig("customButtonImage", "__START_ICON_PATH__");
launcher.writeConfig("alphaSort", "true");
launcher.writeConfig("limitDepth", "true");
launcher.writeConfig("showIconsRootLevel", "true");
launcher.writeConfig("showRecentApps", "false");
launcher.writeConfig("showRecentDocs", "false");

var search = panel.addWidget("org.kde.milou");

var taskManager = panel.addWidget("org.kde.plasma.icontasks");
taskManager.currentConfigGroup = ["General"];
taskManager.writeConfig("launchers", "__TASK_LAUNCHERS__");
taskManager.writeConfig("fill", "false");
taskManager.writeConfig("iconSpacing", "1");
taskManager.writeConfig("groupPopups", "true");

var spacer = panel.addWidget("org.kde.plasma.panelspacer");
spacer.currentConfigGroup = ["General"];
spacer.writeConfig("expanding", "true");

var tray = panel.addWidget("org.kde.plasma.systemtray");
tray.currentConfigGroup = ["General"];
tray.writeConfig("iconSpacing", "1");

var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "true");
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("dateDisplayFormat", "2");
clock.writeConfig("showSeconds", "0");
clock.writeConfig("use24hFormat", "1");

var showDesktop = panel.addWidget("org.kde.plasma.showdesktop");
showDesktop.currentConfigGroup = ["General"];
showDesktop.writeConfig("icon", "desktop-symbolic");

var desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    desktopsArray[j].wallpaperPlugin = "org.kde.image";
}
