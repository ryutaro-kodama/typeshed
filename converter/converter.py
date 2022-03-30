import ast
import xml.etree.ElementTree as ET
import xml.dom.minidom as md


class PythonType2AriadneType:
    string2AriadneString = {
        "bool": "Z", "int": "int", "float": "D", "str": "Lstring",
        "list": "Llist", "set": "Lset", "tuple": "Ltuple", "dict": "Ldict"
    }

    @staticmethod
    def convertString(python_type):
        if python_type in PythonType2AriadneType.string2AriadneString:
            return PythonType2AriadneType.string2AriadneString[python_type]
        else:
            assert 0


class Converter:
    """
    Convert 'Typeshed' type annotation scripts to xml files to recognized by Ariadne.
    """
    def __init__(self, source_path: str, package_name: str):
        self.source_path = source_path
        self.tree = self._parse(source_path)
        self.summary_spec_tag = ET.Element("summary-spec")
        self.class_loader_tag = ET.SubElement(self.summary_spec_tag, "classloader", {"name":"PythonLoader"})
        self.package_name = package_name
        self.function_package_name = f"{self.package_name}/function"
        self.class_package_name = f"{self.package_name}/class"

    def _parse(self, source_path: str) -> ast.AST:
        """Import the python script file and parse to AST.

        Args:
            source_path (str): the path of source script file

        Returns:
            ast.AST: the AST of source script file
        """
        source = open(source_path, mode='r').read()
        tree = ast.parse(source)
        return tree

    def convert(self):
        """The main method of conversion."""
        class_tag = ET.SubElement(
            self.class_loader_tag, "class", {"name":self.package_name, "allocatable":"true"}
        )
        package_func_tag = ET.SubElement(
            self.class_loader_tag, "package", {"name":self.function_package_name}
        )
        package_class_tag = ET.SubElement(
            self.class_loader_tag, "package", {"name":self.class_package_name}
        )

        assert isinstance(self.tree, ast.Module)
        self.convert_global(self.tree.body, class_tag, package_func_tag, package_class_tag)

    def convert_global(
            self, trees: ast.Module, class_tag: ET.Element,
            package_func_tag: ET.Element, package_class_tag: ET.Element):
        """Convert the type annotations of function and classes in global scope.

        Args:
            trees (ast.Module): the ast root of script file
            class_tag (ET.Element): the xml element which will contain the import method xml
            package_func_tag (ET.Element): the xml element in which functions are defined
            package_class_tag (ET.Element): the xml element in which classed are defined
        """
        import_method_tag = ET.SubElement(
            class_tag, "method", {"name":"import", "static":"true", "descriptor":f"()L{self.package_name};"}
        )

        result_var_name = "obj_typeshed_"
        result_var_new_tag = ET.SubElement(
            import_method_tag, "new", {"def":result_var_name, "class":f"L{self.package_name}"}
        )

        for t in trees:
            if isinstance(t, ast.FunctionDef):
                func_name = t.name
                if len(t.decorator_list) > 0:
                    # TODO: There is a decorator
                    pass

                # Create tag in method tag.
                tmp_func_name = f"{func_name}_typeshed_"
                tmp_func_new_tag = ET.SubElement(
                    import_method_tag, "new",
                    {"def":tmp_func_name, "class":f"L{self.function_package_name}/{func_name}"}
                )
                put_tag = ET.SubElement(
                    import_method_tag, "putfield",
                    {"class":"LRoot", "field":func_name, "fieldType":"LRoot",
                     "ref":result_var_name, "value":tmp_func_name}
                )

                # Create class tag in package tag
                func_class_tag = ET.SubElement(
                    package_func_tag, "class", {"name":func_name, "allocatable":"true"}
                )
                do_method_tag = ET.SubElement(
                    func_class_tag, "method",
                    {"name":"do", "descriptor":"()LRoot;", "num_args":str(self._get_num_args(t.args)),
                     "param_names":self._get_arg_names(t.args), "static":"true"}
                )
                self.convert_return(t.returns, do_method_tag)

            elif isinstance(t, ast.AnnAssign):
                # TODO:This may be global variable.
                continue
            elif isinstance(t, ast.Import):
                continue
            elif isinstance(t, ast.ImportFrom):
                continue
            elif isinstance(t, ast.If):
                continue
            else:
                assert 0, t

        return_tag = ET.SubElement(import_method_tag, "return", {"value":result_var_name})

    def _get_num_args(self, args: ast.arguments) -> int:
        """Get the number of arguments

        Args:
            args (ast.arguments): the AST node of arguments

        Returns:
            int: the number of arguments
        """
        return len(args.args) + len(args.kwonlyargs)

    def _get_arg_names(self, args: ast.arguments) -> str:
        """Get the string of formal arguments.

        Args:
            args (ast.arguments): the AST node of arguments

        Returns:
            str: the string of formal arguments
        """
        result = ""
        for arg in args.args:
            result += f"{arg.arg} "
        if len(args.kwonlyargs) != 0:
            for kwarg in args.kwonlyargs:
                result += f"{kwarg.arg} "
        result = result[:-1]
        return result

    def convert_return(self, tree: ast.AST, method_tag: ET.Element):
        """Convert the return type of functions. If the 

        Args:
            tree (ast.AST): the AST of return statement
            method_tag (_type_): the xml element in which this method is defined
        """
        if isinstance(tree, ast.Name):
            return_type = PythonType2AriadneType.convertString(tree.id)
        elif isinstance(tree, ast.Subscript):
            assert isinstance(tree.value, ast.Name)
            return_type = PythonType2AriadneType.convertString(tree.value.id)
        else:
            assert 0

        tmp_var_name = "tmp_ret_typeshed_"
        tmp_var_new_tag = ET.SubElement(method_tag, "new", {"def":tmp_var_name, "class":return_type})

        if isinstance(tree, ast.Subscript):
            # Add element accesses instruction to method tag.
            index = 0
            assert isinstance(tree.slice, ast.Tuple)
            for e in tree.slice.elts:
                assert isinstance(e, ast.Name)
                tmp_elt_var_name = f"tmp_elt_typeshed{index}"
                tmp_elt_new_tag = ET.SubElement(
                    method_tag, "new",
                    {"def":tmp_elt_var_name, "class":PythonType2AriadneType.convertString(e.id)}
                )
                tmp_elt_put_tag = ET.SubElement(
                    method_tag, "putfield",
                    {"class":"LRoot", "field":str(index), "fieldType":"LRoot",
                     "ref":tmp_var_name, "value":tmp_elt_var_name}
                )
                index += 1

        return_tag = ET.SubElement(method_tag, "return", {"value":tmp_var_name})

    def write(self, output_path: str) -> None:
        """Write this xml to `output_path`.

        Args:
            output_path (str): the path of output file
        """
        # Pass xml to 'minidom' with string parsing.
        document = md.parseString(ET.tostring(self.summary_spec_tag, 'utf-8'))

        with open(output_path, 'w') as f:
            # Write DOCTYPE (`<!DOCTYPE summary-spec>`)
            dt = md.getDOMImplementation('').createDocumentType("summary-spec", '', '')
            document.insertBefore(dt, document.documentElement)

            # Write file setting encoding, new line code, whole indent and add indent.
            document.writexml(f, encoding='utf-8', newl='\n', indent='', addindent='  ')


if __name__ == "__main__":
    package_name = "math"

    import os
    current_dir = os.getcwd()

    parser = Converter(f"{current_dir}/../stdlib/{package_name}.pyi", package_name)
    parser.convert()

    parser.write(f"output/{package_name}.xml")