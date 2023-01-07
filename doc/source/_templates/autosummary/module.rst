.. Copyright © 2023 Andrei Tatar <andrei.ttr@gmail.com>
..
.. SPDX-License-Identifier: CC-BY-SA-4.0

{{ fullname | escape | underline}}

.. automodule:: {{ fullname }}

{% block attributes %}
{% if attributes %}
.. rubric:: {{ _('Module Attributes') }}

.. autosummary::
{% for item in attributes %}
   {{ item }}
{%- endfor %}

{% for item in attributes %}
.. autodata:: {{ item }}
{%- endfor %}
{% endif %}
{% endblock %}

{% block functions %}
{% if functions %}
.. rubric:: {{ _('Functions') }}

.. autosummary::
{% for item in functions %}
   {{ item }}
{%- endfor %}

{% for item in functions %}
.. autofunction:: {{ item }}
{%- endfor %}

{% endif %}
{% endblock %}

{% block classes %}
{% if classes %}
.. rubric:: {{ _('Classes') }}

.. autosummary::
{% for item in classes %}
   {{ item }}
{%- endfor %}

{% for item in classes %}
{% if item.endswith('Cmd') %}
.. autoclass:: {{ item }}
   :members:
{% else %}
.. autoclass:: {{ item }}
   :members:
   :inherited-members:
{% endif %}
{%- endfor %}

{% endif %}
{% endblock %}

{% block exceptions %}
{% if exceptions %}
.. rubric:: {{ _('Exceptions') }}

.. autosummary::
{% for item in exceptions %}
   {{ item }}
{%- endfor %}

{% for item in exceptions %}
.. autoexception:: {{ item }}
{%- endfor %}
{% endif %}
{% endblock %}

{% block modules %}
{% if modules %}
.. rubric:: Modules

.. autosummary::
   :toctree:
   :recursive:
{% for item in modules %}
   {{ item }}
{%- endfor %}
{% endif %}
{% endblock %}
