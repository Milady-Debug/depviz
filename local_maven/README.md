Локальное мини-зеркало Maven-репозитория (вымышленные артефакты com.example)
для офлайн-проверки разбора POM: наследование от parent, свойства ${...},
dependencyManagement, импорт BOM, scope test/provided/runtime, optional,
отсутствующий артефакт (com.example:ghost) и цикл core <-> util.
Подключается через URL вида file:///абсолютный/путь/local_maven
