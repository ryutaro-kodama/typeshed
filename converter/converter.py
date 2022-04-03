import ast
from typing import Optional
import xml.etree.ElementTree as ET
import xml.dom.minidom as md


class PythonType2AriadneType:
    string2AriadneString = {
        "bool": "Z", "int": "int", "float": "D", "str": "Lstring",
        "list": "Llist", "set": "Lset", "tuple": "Ltuple", "dict": "Ldict",
        "None": "LNone", "Any": "Lobject"
    }

    @staticmethod
    def convertString(python_type):
        if python_type in PythonType2AriadneType.string2AriadneString:
            return PythonType2AriadneType.string2AriadneString[python_type]
        elif python_type is None:
            return PythonType2AriadneType.string2AriadneString["None"]
        else:
            return f"L{python_type}"


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
        self.tmp_var_name_index = 0

    def _get_tmp_var_name(self) -> str:
        """Return unique var name.

        Returns:
            str: unique variable name
        """
        index = self.tmp_var_name_index
        self.tmp_var_name_index += 1
        return f"_typeshed{index}"

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
        # Create the class tag and import method tag directly under of 'classloader' tag.
        class_tag = ET.SubElement(
            self.class_loader_tag, "class", {"name":self.package_name, "allocatable":"true"}
        )
        import_method_tag = ET.SubElement(
            class_tag, "method", {"name":"import", "static":"true", "descriptor":f"()L{self.package_name};"}
        )

        # Create the package to define global functions.
        function_package_name = f"{self.package_name}/function"
        function_package_tag = ET.SubElement(
            self.class_loader_tag, "package", {"name":function_package_name}
        )
        
        # Create the package to define global classes.
        class_package_name = f"{self.package_name}/class"
        class_package_tag = ET.SubElement(
            self.class_loader_tag, "package", {"name":class_package_name}
        )

        assert isinstance(self.tree, ast.Module)

        # Create tag of return object (, which is put method objects to). 
        return_obj_name = "obj_typeshed_"
        return_obj_new_tag = ET.SubElement(
            import_method_tag, "new", {"def":return_obj_name, "class":f"L{self.package_name}"}
        )
        
        # Convert each functions and classes.
        for tree in self.tree.body:
            self.convert_global(
                tree, import_method_tag, return_obj_name,
                function_package_tag, function_package_name,
                class_package_tag, class_package_name
            )

        # Create return tag of return object.
        return_tag = ET.SubElement(import_method_tag, "return", {"value":return_obj_name})

    def convert_global(
            self, tree: ast.AST, def_method_tag: ET.Element, return_obj_name: str,
            function_def_package_tag: ET.Element, function_def_package_name: str,
            class_def_package_tag: ET.Element, class_def_package_name: str):
        """Convert the type annotations of function and classes in global scope.

        Args:
            trees (ast.Module): the ast root of script file
            class_tag (ET.Element): the xml element which will contain the import method xml
            package_func_tag (ET.Element): the xml element in which functions are defined
            package_class_tag (ET.Element): the xml element in which classed are defined
        """
        if isinstance(tree, ast.FunctionDef):
            func_name = tree.name

            # TODO: There is a decorator
            for d in tree.decorator_list:
                assert isinstance(d, ast.Name)
                if d.id == "overload":
                    # TODO: There is a overload. If there are two variables in single scope,
                    # XMLParser can't parse, so do nothing.
                    return

            # Create tag in method tag (create function object and put field).
            tmp_func_name = f"{func_name}_typeshed_"
            tmp_func_new_tag = ET.SubElement(
                def_method_tag, "new",
                {"def":tmp_func_name, "class":f"L{function_def_package_name}/{func_name}"}
            )
            put_tag = ET.SubElement(
                def_method_tag, "putfield",
                {"class":"LRoot", "field":func_name, "fieldType":"LRoot",
                 "ref":return_obj_name, "value":tmp_func_name}
            )

            # Create class tag (function defining) in package tag.
            func_class_tag = ET.SubElement(
                function_def_package_tag, "class", {"name":func_name, "allocatable":"true"}
            )
            do_method_tag = ET.SubElement(
                func_class_tag, "method",
                {"name":"do", "descriptor":"()LRoot;", "num_args":str(self._get_num_args(tree.args)),
                 "param_names":self._get_arg_names(tree.args), "static":"true"}
            )

            # Convert return type.
            self.convert_return(tree.returns, do_method_tag)

        elif isinstance(tree, ast.ClassDef):
            # TODO: Handle base classes.

            class_name = tree.name

            # Create tag in method tag (create class object and put field).
            tmp_class_name = f"{class_name}_typeshed_"
            tmp_class_new_tag = ET.SubElement(
                def_method_tag, "new",
                {"def":tmp_class_name, "class":f"L{class_def_package_name}/{class_name}"}
            )
            put_tag = ET.SubElement(
                def_method_tag, "putfield",
                {"class":"LRoot", "field":class_name, "fieldType":"LRoot",
                 "ref":return_obj_name, "value":tmp_class_name}
            )

            # Create package tag of this class.
            method_define_package_name = f"{self.package_name}/{class_name}"
            method_define_package_tag = ET.SubElement(
                self.class_loader_tag, "package", {"name":method_define_package_name}
            )

            # Create class tags for methods defining in '~/class' package.
            class_body_tag = ET.SubElement(
                class_def_package_tag, "class",
                {"name":class_name, "allocatable":"true"}
            )
            do_method_tag = ET.SubElement(
                class_body_tag, "method",
                {"name":"do", "descriptor":"()LRoot;"}
            )
            result_obj_name = class_name + "_typeshed_"
            result_obj = ET.SubElement(
                do_method_tag, "new",
                {"def":tmp_class_name, "class":f"L{class_def_package_name}/{class_name}"}
            )

            # Convert methods and inner classes.
            for inner_tree in tree.body:
                self.convert_global(
                    inner_tree, do_method_tag, result_obj_name,
                    method_define_package_tag, method_define_package_name,
                    class_def_package_tag, class_def_package_name
                )

            # Create return object tag.
            return_result_obj_tag = ET.SubElement(do_method_tag, "return", {"value":result_obj_name})
        elif isinstance(tree, ast.Assign):
            # TODO:This may be global variable.
            pass
        elif isinstance(tree, ast.AnnAssign):
            assert isinstance(tree.target, ast.Name)
            var_name = tree.target.id

            # Create field variable tag.
            tmp_var_name = var_name + "_typeshed_"
            tmp_var_type = self._get_expr_type(tree.annotation)
            tmp_var_def_tag = ET.SubElement(
                def_method_tag, "new", {"def":tmp_var_name, "class":tmp_var_type}
            )

            # Set the field variable to object.
            put_tag = ET.SubElement(
                def_method_tag, "putfield",
                {"class":"LRoot", "field":var_name, "fieldType":"LRoot",
                 "ref":return_obj_name, "value":tmp_var_name}
            )
        elif isinstance(tree, ast.Import):
            pass
        elif isinstance(tree, ast.ImportFrom):
            pass
        elif isinstance(tree, ast.If):
            pass
        elif isinstance(tree, ast.Expr):
            pass
        else:
            assert 0, tree

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
        return_var_name = self._convert_expr(tree, method_tag)
        return_tag = ET.SubElement(method_tag, "return", {"value":return_var_name})

    def _get_expr_type(self, tree: ast.AST) -> str:
        """Get string of type from AST.

        Args:
            tree (ast.AST): the AST

        Returns:
            str: the string of type
        """
        if isinstance(tree, ast.Name):
            expr_type = PythonType2AriadneType.convertString(tree.id)
        elif isinstance(tree, ast.Subscript):
            expr_type = self._get_expr_type(tree.value)
        elif isinstance(tree, ast.BinOp):
            expr_type_left = self._get_expr_type(tree.left)
            expr_type_right = self._get_expr_type(tree.right)
            expr_type = expr_type_left + " " + expr_type_right
        elif isinstance(tree, ast.Constant):
            expr_type = PythonType2AriadneType.convertString(tree.value)
        else:
            assert 0, tree
        
        return expr_type

    def _convert_expr(
            self, tree: ast.AST, parent_tag: ET.Element, put_var_name:Optional[str]=None, index:int=0):
        """Convert expression from AST, in which new tags are inserted into 'parent_tag'. If the new 
        object is put to an object, the put object's name is 'put_var_name' and the field index is 
        'index'

        Args:
            tree (ast.AST): the AST
            parent_tag (ET.Element): the tag which these new tags are inserted
            put_var_name (Optional[str]): the object to which these new objects are putted.
                Defaults to None.
            index (int): the field index of which these new objects are putted. Defaults to 0.

        Returns:
            _type_: _description_
        """
        new_var_name = self._get_tmp_var_name()
        if isinstance(tree, ast.Tuple):
            inner_subscript_type = PythonType2AriadneType.convertString("tuple")
            inner_subscript_new_tag = ET.SubElement(
                parent_tag, "new", {"def":new_var_name, "class":inner_subscript_type}
            )

            elt_index = 0
            for e in tree.elts:
                self._convert_expr(e, parent_tag, new_var_name, elt_index)
                elt_index += 1
        elif isinstance(tree, ast.List):
            inner_subscript_type = PythonType2AriadneType.convertString("list")
            inner_subscript_new_tag = ET.SubElement(
                parent_tag, "new", {"def":new_var_name, "class":inner_subscript_type}
            )

            elt_index = 0
            for e in tree.elts:
                self._convert_expr(e, parent_tag, new_var_name, elt_index)
                elt_index += 1
        elif isinstance(tree, ast.Subscript):
            inner_subscript_type = self._get_expr_type(tree.value)
            inner_subscript_new_tag = ET.SubElement(
                parent_tag, "new", {"def":new_var_name, "class":inner_subscript_type}
            )

            if isinstance(tree.slice, ast.Tuple) or isinstance(tree.slice, ast.List):
                elt_index = 0
                for e in tree.slice.elts:
                    self._convert_expr(e, parent_tag, new_var_name, elt_index)
                    elt_index += 1
            else:
                self._convert_expr(tree.slice, parent_tag, new_var_name)
        else:
            var_type = self._get_expr_type(tree)

            var_new_tag = ET.SubElement(
                parent_tag, "new", {"def":new_var_name, "class":var_type}
            )

        if put_var_name is not None:
            var_put_tag = ET.SubElement(
                parent_tag, "putfield",
                {"class":"LRoot", "field":str(index), "fieldType":"LRoot",
                 "ref":put_var_name, "value":new_var_name}
            )
        
        return new_var_name

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