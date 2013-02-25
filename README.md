Using r2 cli
==

**Show all nodes:**

    r2 node show

**Show details about a particular node:**

    r2 node show <node id>

**Show all adventures:**

    r2 adventure show

**Show details about a particular adventure:**

    r2 adventure show <adventure id>

**Show adventures a node can execute:**

    r2 node show <node id> adventures

**Execute an adventure on a particular node:**

    r2 adventure execute <adventure id> --node=<node id>

**Show all tasks:**

    r2 task show

**Show details about a particular task:**

    r2 task show <task id>

**Override opencenter server endpoint:**

    OPENCENTER_ENDPOINT=http://<opencenter server>:8080 r2 node show

or:

    r2 node show --endpoint=http://<opencenter server>:8080

Using opencentercli
==

**Get help:**

    opencentercli --help
    opencentercli node --help
    opencentercli node create --help

**Show all nodes:**

    opencentercli node list

**Show details about a particular node:**

    opencentercli node show <node id>

**Show all adventures:**

    opencentercli adventure list

**Show details about a particular adventure:**

    opencentercli adventure show <adventure id>

**Show adventures a node can execute:**

    opencentrecli adventures <node id>

**Execute an adventure on a particular node:**

    opencentercli adventure execute <node id> <adventure id>

**Show all tasks:**

    opencentercli task list

**Show details about a particular task:**

    opencentercli task show <task id>

**List items that match a filter**

    opencentercli node filter 'id=6'

**Override opencenter server endpoint:**

    OPENCENTER_ENDPOINT=http://<opencenter server>:8080 opencentercli node list
